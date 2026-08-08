"""
Bug-hunt tests — core modules wave B (TDD RED->GREEN).

Real bugs hunted (each has a failing test first, then a minimal source fix):

  A. canvas_logic_service.run() never issues a sandbox policy (fail-open).
     PolicyIssuer.issue() is called with a phantom `tier=` kwarg (legacy path)
     and without the required `agent_id` (scopes path) -> TypeError -> caught
     -> policy=None -> execute_python runs with NO policy, so the per-canvas
     FS containment (fs_root) is never applied.
  B. mini_app_service.run_stateful storage ops attribute MiniAppAsset rows to
     app.created_by instead of the acting user (record ops DO use user_id).
  C. mini_app_service.validate_manifest raises AttributeError (500) instead of
     ValueError (400) when manifest.storage / manifest.db are non-objects.
  D. atom_saas_websocket._reconnect spawns detached child tasks -> parallel
     reconnect chains -> duplicate connections / attempts exceed the cap.
  E. mini_app_service.run_stateful returns str(e) for RuntimeError -> internal
     env var names/values + filesystem paths leak into agent-visible errors.
"""
import asyncio
import contextlib
import json
import uuid

import pytest
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from core.models import (
    AgentRegistry, Canvas, CanvasLogic, CanvasState, MiniApp, MiniAppAsset,
)


def _make_miniapp(db, name="bugapp", manifest_extra=None, user="u1"):
    """Create a canvas + logic + app + state tuple for run_stateful tests."""
    canvas_id = f"c-{uuid.uuid4().hex[:12]}"
    app_id = f"app-{uuid.uuid4().hex[:12]}"
    manifest = {
        "declared_scopes": ["*"],
        "skills": [], "mcp_servers": [], "entrypoint": "logic",
        "dependencies": [], "base_image": "python:3.11-slim", "assets": [],
        "storage": {"enabled": True, "backend": "local",
                    "max_bytes_per_object": 5 * 1024 * 1024},
        "db": {"enabled": True, "record_queries": []},
        "initial_state": {}, "blueprint": {},
    }
    if manifest_extra:
        manifest.update(manifest_extra)
    db.add(Canvas(
        id=canvas_id, tenant_id="t1", created_by=user, name=name,
        canvas_type="mini_app", content={"blocks": []}, style={}, status="active",
        mini_app_id=app_id,
    ))
    db.add(CanvasLogic(canvas_id=canvas_id, language="python",
                       source="state = state", created_by=user))
    db.add(MiniApp(
        id=app_id, tenant_id="t1", workspace_id="w1", created_by=user, name=name,
        manifest=manifest, blueprint_canvas_id=canvas_id, status="draft",
    ))
    db.add(CanvasState(canvas_id=canvas_id, tenant_id="t1", state={}, version=1))
    db.commit()
    return app_id, canvas_id


def _patch_db(monkeypatch, db_session):
    @contextlib.contextmanager
    def _cm():
        yield db_session
    monkeypatch.setattr("core.database.get_db_session", _cm)


def _patch_run_support(monkeypatch, db_session, envelope):
    _patch_db(monkeypatch, db_session)

    class FakeRuntime:
        async def execute_python(self, code, *, policy=None, inputs=None, cwd=None,
                                 image=None, callback_handler=None, **kwargs):
            return SimpleNamespace(
                success=True, stdout="", stderr="", exit_code=0,
                metadata={"state_envelope": envelope},
            )

    monkeypatch.setattr("core.mini_app_service.get_miniapp_runtime",
                        lambda: FakeRuntime())
    monkeypatch.setattr("core.mini_app_storage.get_max_object_bytes",
                        lambda: 1024 * 1024)
    monkeypatch.setattr("core.mini_app_storage.get_mini_app_storage",
                        lambda tenant, canvas: _FakeStorage())
    monkeypatch.setattr("core.mini_app_service._broadcast_state", AsyncMock())
    monkeypatch.setattr("core.mini_app_service._broadcast_db", AsyncMock())


class _FakeStorage:
    def __init__(self):
        self._data = {}

    def store(self, key, data, content_type=None):
        self._data[key] = data
        return f"fake://{key}"

    def retrieve(self, key):
        return self._data.get(key)

    def delete(self, key):
        return self._data.pop(key, None) is not None


# ============================================================================
# Bug A — canvas_logic_service: sandbox policy never issued (fail-open)
# ============================================================================

class TestCanvasLogicPolicyIssued:
    @pytest.mark.asyncio
    async def test_run_with_scopes_issues_policy_with_tool_whitelist(self, db_session, monkeypatch):
        """run(scopes=...) must pass a REAL issued policy (fs roots + scopes
        whitelist) to the runtime — never None (fail-open)."""
        from core import canvas_logic_service as cls

        captured = {}

        class FakeRuntime:
            async def execute_python(self, code, *, policy=None, inputs=None, cwd=None):
                captured["policy"] = policy
                captured["cwd"] = cwd
                return SimpleNamespace(success=True, stdout="ok", stderr="", exit_code=0)

        monkeypatch.setattr(cls, "get_runtime", lambda: FakeRuntime())
        db_session.add(AgentRegistry(
            id="a-auto-1", name="Auto", category="Ops", module_path="x",
            class_name="y", status="AUTONOMOUS",
        ))
        db_session.commit()
        svc = cls.CanvasLogicService(db_session)
        svc.save_logic(canvas_id="c-policy-1", source="x = 1", created_by="u1")

        await svc.run("c-policy-1", inputs={}, agent_id="a-auto-1",
                      scopes=("canvas_render",))

        policy = captured["policy"]
        assert policy is not None, (
            "run() executed WITHOUT a sandbox policy (fail-open): "
            "per-canvas FS containment was never applied"
        )
        assert policy.tool_whitelist == ("canvas_render",)
        import os
        fs_root = os.path.join(cls.CANVAS_RUNTIME_ROOT, "c-policy-1")
        assert os.path.abspath(policy.fs_roots[0]) == os.path.abspath(fs_root)

    @pytest.mark.asyncio
    async def test_run_legacy_path_issues_policy(self, db_session, monkeypatch):
        """run() without scopes must also pass a real policy (legacy path
        called issue(tier=...) — a phantom kwarg that always raised)."""
        from core import canvas_logic_service as cls

        captured = {}

        class FakeRuntime:
            async def execute_python(self, code, *, policy=None, inputs=None, cwd=None):
                captured["policy"] = policy
                return SimpleNamespace(success=True, stdout="ok", stderr="", exit_code=0)

        monkeypatch.setattr(cls, "get_runtime", lambda: FakeRuntime())
        svc = cls.CanvasLogicService(db_session)
        svc.save_logic(canvas_id="c-policy-2", source="x = 1", created_by="u1")

        await svc.run("c-policy-2", inputs={}, agent_id=None)

        policy = captured["policy"]
        assert policy is not None, "legacy canvas run executed with no policy"
        assert policy.tier_at_issuance == "autonomous"


# ============================================================================
# Bug B — mini_app_service: storage-op assets attributed to app author,
#         not the acting user
# ============================================================================

class TestStorageOpAttribution:
    @pytest.mark.asyncio
    async def test_storage_op_asset_attributed_to_acting_user(self, db_session, monkeypatch):
        """MiniAppAsset.created_by must be the RUN's actor (user_id), matching
        record-op attribution — not the app author's id."""
        app_id, canvas_id = _make_miniapp(db_session, user="app-author")
        envelope = {
            "state": {"n": 1},
            "storage_ops": [
                {"op": "put", "key": "k1", "data": "hello", "content_type": "text/plain"},
            ],
            "record_ops": [],
        }
        _patch_run_support(monkeypatch, db_session, envelope)

        from core.mini_app_service import run_stateful

        result = await run_stateful(canvas_id, agent_id="a1", user_id="actor-9")
        assert result["success"], result

        asset = (
            db_session.query(MiniAppAsset)
            .filter(MiniAppAsset.canvas_id == canvas_id, MiniAppAsset.key == "k1")
            .first()
        )
        assert asset is not None
        assert asset.created_by == "actor-9", (
            f"asset attributed to {asset.created_by!r}, expected the acting "
            "user 'actor-9' (app author is 'app-author')"
        )


# ============================================================================
# Bug C — mini_app_service.validate_manifest crashes with AttributeError
#         instead of ValueError for malformed storage/db sections
# ============================================================================

class TestManifestValidationErrorContract:
    @pytest.mark.parametrize("bad_storage", ["not-a-dict", ["x"], 42])
    def test_storage_non_object_raises_value_error(self, bad_storage):
        from core.mini_app_service import validate_manifest

        with pytest.raises(ValueError):
            validate_manifest({
                "declared_scopes": ["canvas_render"],
                "dependencies": [],
                "storage": bad_storage,
            })

    @pytest.mark.parametrize("bad_db", ["not-a-dict", ["x"], 42])
    def test_db_non_object_raises_value_error(self, bad_db):
        from core.mini_app_service import validate_manifest

        with pytest.raises(ValueError):
            validate_manifest({
                "declared_scopes": ["canvas_render"],
                "dependencies": [],
                "db": bad_db,
            })


# ============================================================================
# Bug D — atom_saas_websocket: detached reconnect chains spawn parallel
#         reconnect loops -> duplicate connections beyond the attempts cap
# ============================================================================

class TestReconnectChainSingle:
    @pytest.mark.asyncio
    async def test_no_parallel_reconnect_chains(self, monkeypatch):
        """Two disconnect events while a reconnect chain is active must NOT
        double the connection attempts: total connect() calls stays within
        MAX_RECONNECT_ATTEMPTS (single chain)."""
        from core.atom_saas_websocket import AtomSaaSWebSocketClient

        client = AtomSaaSWebSocketClient(api_token="tok")
        client.MAX_RECONNECT_ATTEMPTS = 6
        client.RECONNECT_DELAYS = [0.02, 0.02, 0.02, 0.02, 0.02]
        client._update_db_state = AsyncMock()

        connect_calls = []

        async def failing_connect(*args, **kwargs):
            connect_calls.append(1)
            raise OSError("connection refused")

        monkeypatch.setattr("core.atom_saas_websocket.websockets.connect",
                            failing_connect)

        # First disconnect spawns chain A; wait for its original task to
        # complete (a detached child chain keeps running).
        await client._handle_disconnect("first")
        await asyncio.sleep(0.05)
        # Second disconnect while the detached chain is still active.
        await client._handle_disconnect("second")
        await asyncio.sleep(0.5)

        assert len(connect_calls) <= client.MAX_RECONNECT_ATTEMPTS + 1, (
            f"{len(connect_calls)} connection attempts for "
            f"MAX_RECONNECT_ATTEMPTS={client.MAX_RECONNECT_ATTEMPTS} — "
            "parallel reconnect chains are double-spawning"
        )


# ============================================================================
# Bug E — mini_app_service.run_stateful leaks internal paths / env names
#         in RuntimeError messages returned to the agent
# ============================================================================

class TestRuntimeErrorNoLeak:
    @pytest.mark.asyncio
    async def test_runtime_error_message_is_generic(self, db_session, monkeypatch):
        """A RuntimeError from get_miniapp_runtime (e.g. Firecracker
        provisioning) must not leak env var names, values, or FS paths into
        the returned error string."""
        app_id, canvas_id = _make_miniapp(db_session)
        _patch_db(monkeypatch, db_session)
        monkeypatch.setattr(
            "core.mini_app_service.get_miniapp_runtime",
            lambda: (_ for _ in ()).throw(
                RuntimeError(
                    "Mini apps require the Firecracker runtime, but "
                    "ATOM_MINIAAP_RUNTIME='docker'. "
                    "FIRECRACKER_KERNEL_IMAGE=/var/run/fc/vmlinux is missing."
                )
            ),
        )

        from core.mini_app_service import run_stateful

        result = await run_stateful(canvas_id)
        assert not result["success"]
        error = result.get("error", "")
        assert "/var/run" not in error
        assert "ATOM_MINIAAP_RUNTIME" not in error
        assert "FIRECRACKER_KERNEL_IMAGE" not in error
        assert error, "expected a generic error string"
