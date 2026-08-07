"""Mini-app data layer — record_ops envelope + read-bridge pre-fetch tests.

All Firecracker execution is mocked (no real VM in CI). Covers:
_validate_record_op matrix, envelope execution + caps + dry-run + kill switch,
and the read-bridge injectors (record_queries, documents.search, mcp_servers).
"""
import contextlib
import json
import uuid

import pytest

from core.models import Canvas, CanvasLogic, CanvasState, MiniApp, MiniAppAsset


def _make_app(db, name="store", manifest_extra=None):
    canvas_id = f"c-{uuid.uuid4().hex[:12]}"
    app_id = f"app-{uuid.uuid4().hex[:12]}"
    manifest = {
        "declared_scopes": ["*"],
        "skills": [], "mcp_servers": [], "entrypoint": "logic",
        "dependencies": [], "base_image": "python:3.11-slim", "assets": [],
        "storage": {"enabled": True, "backend": "local", "max_bytes_per_object": 5 * 1024 * 1024},
        "initial_state": {}, "blueprint": {},
    }
    if manifest_extra:
        manifest.update(manifest_extra)
    db.add(Canvas(
        id=canvas_id, tenant_id="t1", created_by="u1", name=name,
        canvas_type="mini_app", content={"blocks": []}, style={}, status="active",
        mini_app_id=app_id,
    ))
    db.add(CanvasLogic(canvas_id=canvas_id, language="python", source="state = state", created_by="u1"))
    db.add(MiniApp(
        id=app_id, tenant_id="t1", workspace_id="w1", created_by="u1", name=name,
        manifest=manifest, blueprint_canvas_id=canvas_id, status="draft",
    ))
    db.add(CanvasState(canvas_id=canvas_id, tenant_id="t1", state={}, version=1))
    db.commit()
    return app_id, canvas_id


@pytest.fixture
def canvas_fixture(db_session):
    return _make_app(db_session)


def _patch_db(monkeypatch, db_session):
    @contextlib.contextmanager
    def _cm():
        yield db_session
    monkeypatch.setattr("core.database.get_db_session", _cm)


def _fake_runtime(monkeypatch, envelope, image_log=None):
    import core.mini_app_service as svc

    class FakeRuntime:
        async def execute_python(self, code, *, policy=None, inputs=None, cwd=None, image=None, callback_handler=None, **kwargs):
            if image_log is not None:
                image_log.append(image)
            res = type("R", (), {
                "success": True, "exit_code": 0, "stderr": "",
                "stdout": "__MINIAPP_STATE__:" + json.dumps(envelope),
                "metadata": {},
            })()
            return res
    monkeypatch.setattr(svc, "get_miniapp_runtime", FakeRuntime)


# ---------------------------------------------------------------------------
# _validate_record_op
# ---------------------------------------------------------------------------
class TestValidateRecordOp:
    def _v(self, op):
        from core.mini_app_service import _validate_record_op
        return _validate_record_op(op, max_record_bytes=1024)

    def test_valid_ops(self):
        assert self._v({"op": "append", "series": "chart_data", "data": {"v": 1}})["op"] == "append"
        assert self._v({"op": "append", "series": "s", "data": {}, "id": "custom"})["id"] == "custom"
        assert self._v({"op": "query", "series": "s", "limit": 50, "order": "asc"})["op"] == "query"
        assert self._v({"op": "count", "series": "s", "filter": {"k": 1}})["op"] == "count"
        assert self._v({"op": "update", "series": "s", "id": "r1", "data": {"x": 2}})["op"] == "update"
        assert self._v({"op": "update_many", "series": "s", "filter": {"k": 1}, "data": {"x": 2}})["op"] == "update_many"
        assert self._v({"op": "delete", "series": "s", "id": "r1"})["op"] == "delete"
        assert self._v({"op": "delete_series", "series": "s"})["op"] == "delete_series"
        assert self._v({"op": "clear"})["op"] == "clear"
        assert self._v({"op": "list_series"})["op"] == "list_series"
        assert self._v({"op": "get", "series": "s", "id": "r1"})["op"] == "get"

    def test_rejects_bad(self):
        assert self._v({"op": "drop_table"}) is None
        assert self._v("nope") is None
        assert self._v({"op": "append"}) is None                      # no series
        assert self._v({"op": "append", "series": "Bad", "data": {}}) is None
        assert self._v({"op": "append", "series": "s", "data": [1]}) is None     # non-dict
        assert self._v({"op": "append", "series": "s", "data": {"big": "x" * 4096}}) is None  # oversize
        assert self._v({"op": "query", "series": "s", "limit": 0}) is None
        assert self._v({"op": "query", "series": "s", "limit": 99999}) is None
        assert self._v({"op": "query", "series": "s", "order": "up"}) is None
        assert self._v({"op": "query", "series": "s", "filter": {"nested": {"a": 1}}}) is None
        assert self._v({"op": "update", "series": "s", "data": {"x": 1}}) is None  # no id
        assert self._v({"op": "delete", "series": "s"}) is None                   # no id
        assert self._v({"op": "delete_series"}) is None                           # no series


# ---------------------------------------------------------------------------
# run_stateful record_ops envelope
# ---------------------------------------------------------------------------
class TestRunRecordOps:
    @pytest.mark.asyncio
    async def test_append_persists_and_bumps_seq(self, db_session, canvas_fixture, monkeypatch):
        import core.mini_app_service as svc
        from core.models import CanvasRecord
        app_id, canvas_id = canvas_fixture
        _fake_runtime(monkeypatch, {
            "state": {},
            "storage_ops": [],
            "record_ops": [
                {"op": "append", "series": "chart_data", "data": {"label": "Jan", "value": 12}},
                {"op": "append", "series": "chart_data", "data": {"label": "Feb", "value": 20}},
            ],
        })
        _patch_db(monkeypatch, db_session)
        result = await svc.run_stateful(canvas_id, user_id="u1", scopes=("*",))
        assert result["success"]
        assert len(result["record_results"]) == 2
        assert all(r["ok"] for r in result["record_results"])
        assert [r["seq"] for r in result["record_results"]] == [1, 2]
        rows = db_session.query(CanvasRecord).filter(
            CanvasRecord.canvas_id == canvas_id, CanvasRecord.series == "chart_data"
        ).all()
        assert len(rows) == 2
        assert rows[0].seq == 1 and rows[0].data["label"] == "Jan"
        assert rows[0].app_id == app_id and rows[0].tenant_id == "t1"

    @pytest.mark.asyncio
    async def test_query_op_reads_back(self, db_session, canvas_fixture, monkeypatch):
        import core.mini_app_service as svc
        from core.mini_app_db_service import append_record
        app_id, canvas_id = canvas_fixture
        append_record(db_session, canvas_id, "t1", app_id, "chart_data", {"label": "Jan", "value": 12})
        _fake_runtime(monkeypatch, {
            "state": {},
            "record_ops": [{"op": "query", "series": "chart_data", "limit": 10}],
        })
        _patch_db(monkeypatch, db_session)
        result = await svc.run_stateful(canvas_id, user_id="u1", scopes=("*",))
        got = result["record_results"][0]
        assert got["ok"] and got["count"] == 1
        assert got["records"][0]["data"]["label"] == "Jan"

    @pytest.mark.asyncio
    async def test_update_delete_roundtrip(self, db_session, canvas_fixture, monkeypatch):
        import core.mini_app_service as svc
        from core.mini_app_db_service import append_record
        from core.models import CanvasRecord
        app_id, canvas_id = canvas_fixture
        r = append_record(db_session, canvas_id, "t1", app_id, "s", {"x": 1})
        _fake_runtime(monkeypatch, {
            "state": {},
            "record_ops": [
                {"op": "update", "series": "s", "id": r["id"], "data": {"y": 2}},
                {"op": "delete", "series": "s", "id": r["id"]},
            ],
        })
        _patch_db(monkeypatch, db_session)
        result = await svc.run_stateful(canvas_id, user_id="u1", scopes=("*",))
        assert result["record_results"][0]["ok"]
        assert result["record_results"][1]["ok"]
        assert db_session.query(CanvasRecord).filter(CanvasRecord.canvas_id == canvas_id).count() == 0

    @pytest.mark.asyncio
    async def test_invalid_op_skipped_not_crashing(self, db_session, canvas_fixture, monkeypatch):
        import core.mini_app_service as svc
        _fake_runtime(monkeypatch, {
            "state": {},
            "record_ops": [{"op": "evil"}, {"op": "append", "series": "s", "data": {"x": 1}}],
        })
        _patch_db(monkeypatch, db_session)
        result = await svc.run_stateful(canvas_fixture[1], user_id="u1", scopes=("*",))
        assert result["success"]
        assert len(result["record_results"]) == 1  # only the valid op executed

    @pytest.mark.asyncio
    async def test_manifest_disabled_rejects_all(self, db_session, canvas_fixture, monkeypatch):
        import core.mini_app_service as svc
        from core.models import MiniApp
        app_id, canvas_id = canvas_fixture
        app = db_session.query(MiniApp).filter(MiniApp.id == app_id).first()
        new_manifest = dict(app.manifest)
        new_manifest["db"] = {"enabled": False}
        app.manifest = new_manifest
        db_session.commit()
        _fake_runtime(monkeypatch, {
            "state": {}, "record_ops": [{"op": "append", "series": "s", "data": {"x": 1}}],
        })
        _patch_db(monkeypatch, db_session)
        result = await svc.run_stateful(canvas_id, user_id="u1", scopes=("*",))
        assert result["record_results"][0] == {"op": "append", "ok": False, "error": "db_disabled"}

    @pytest.mark.asyncio
    async def test_kill_switch_rejects_all(self, db_session, canvas_fixture, monkeypatch):
        import core.mini_app_service as svc
        monkeypatch.setenv("ATOM_MINIAPP_DB_ENABLED", "false")
        _fake_runtime(monkeypatch, {
            "state": {}, "record_ops": [{"op": "append", "series": "s", "data": {"x": 1}}],
        })
        _patch_db(monkeypatch, db_session)
        result = await svc.run_stateful(canvas_fixture[1], user_id="u1", scopes=("*",))
        assert result["record_results"][0]["error"] == "db_disabled"

    @pytest.mark.asyncio
    async def test_dev_run_proposes_without_committing(self, db_session, canvas_fixture, monkeypatch):
        import core.mini_app_service as svc
        from core.models import CanvasRecord
        _, canvas_id = canvas_fixture
        _fake_runtime(monkeypatch, {
            "state": {}, "record_ops": [{"op": "append", "series": "s", "data": {"x": 1}}],
        })
        _patch_db(monkeypatch, db_session)
        result = await svc.run_stateful(canvas_id, user_id="u1", scopes=("*",), persist=False)
        assert result["proposed_record_ops"][0]["proposed"] is True
        assert db_session.query(CanvasRecord).filter(CanvasRecord.canvas_id == canvas_id).count() == 0

    @pytest.mark.asyncio
    async def test_broadcast_fired_on_committed_writes(self, db_session, canvas_fixture, monkeypatch):
        import core.mini_app_service as svc
        calls = []

        class FakeManager:
            async def broadcast(self, channel, msg):
                calls.append((channel, msg))

        monkeypatch.setattr("core.websockets.manager", FakeManager())
        _fake_runtime(monkeypatch, {
            "state": {}, "record_ops": [{"op": "append", "series": "s", "data": {"x": 1}}],
        })
        _patch_db(monkeypatch, db_session)
        result = await svc.run_stateful(canvas_fixture[1], user_id="u1", scopes=("*",))
        assert result["success"]
        db_msgs = [m for ch, m in calls if m.get("data", {}).get("action") == "mini_app_db"]
        assert len(db_msgs) == 1
        assert db_msgs[0]["data"]["ops"][0]["op"] == "append"


# ---------------------------------------------------------------------------
# Guest agent envelope harvest
# ---------------------------------------------------------------------------
class TestGuestAgentHarvest:
    def test_record_ops_harvested_from_globals(self):
        from core.sandbox_runtime.firecracker_guest import agent as guest
        code = (
            "state = {'n': 1}\n"
            "record_ops.append({'op': 'append', 'series': 's', 'data': {'x': 1}})\n"
        )
        result = guest.run_code(code, {"state": {}, "record_ops": [], "storage_ops": []})
        env = result["state_envelope"]
        assert env["record_ops"] == [{"op": "append", "series": "s", "data": {"x": 1}}]

    def test_record_ops_absent_is_empty(self):
        from core.sandbox_runtime.firecracker_guest import agent as guest
        result = guest.run_code("state = {}; storage_ops.append({'op': 'put', 'key': 'k', 'data': 'v'})",
                                {"state": {}, "storage_ops": []})
        env = result["state_envelope"]
        assert env["record_ops"] == []
        assert env["storage_ops"][0]["op"] == "put"


# ---------------------------------------------------------------------------
# Read bridge
# ---------------------------------------------------------------------------
class TestReadBridge:
    def test_record_queries_prefetch(self, db_session, canvas_fixture):
        import core.mini_app_service as svc
        from core.mini_app_db_service import append_record
        app_id, canvas_id = canvas_fixture
        append_record(db_session, canvas_id, "t1", app_id, "todos", {"task": "a"})
        append_record(db_session, canvas_id, "t1", app_id, "todos", {"task": "b"})
        manifest = {"db": {"record_queries": ["todos"]}}
        out = svc._inject_record_queries(manifest, db_session, canvas_id)
        assert [r["data"]["task"] for r in out["todos"]] == ["b", "a"]  # desc latest-first

    def test_record_queries_empty_manifest(self, db_session, canvas_fixture):
        import core.mini_app_service as svc
        assert svc._inject_record_queries({}, db_session, canvas_fixture[1]) == {}

    @pytest.mark.asyncio
    async def test_documents_search_injected(self, monkeypatch):
        import core.mini_app_service as svc

        class FakeRegistry:
            async def execute_action(self, name, args, context):
                assert name == "documents.search"
                assert args["query"] == "revenue"
                return {"success": True, "data": {"results": [{"title": "Q1", "snippet": "..."}]}}

        monkeypatch.setattr("core.action_registry.action_registry", FakeRegistry())
        out = await svc._inject_data_sources(
            {"data_sources": [{"type": "documents.search", "query": "revenue"}]},
            "t1", "w1", "ag1",
        )
        assert out["documents"] == [{"title": "Q1", "snippet": "..."}]

    @pytest.mark.asyncio
    async def test_documents_search_failure_skipped(self, monkeypatch):
        import core.mini_app_service as svc

        class BoomRegistry:
            async def execute_action(self, name, args, context):
                raise RuntimeError("boom")

        monkeypatch.setattr("core.mini_app_service._safe_action_call",
                            lambda registry, name, args, context: _boom())
        out = await svc._inject_data_sources(
            {"data_sources": [{"type": "documents.search", "query": "x"}]}, "t1", "w1", "ag1"
        )
        assert out == {}

    @pytest.mark.asyncio
    async def test_mcp_source_injected_with_credentials(self, db_session, monkeypatch):
        """Integration pre-fetch routes through the unified dispatcher."""
        import core.mini_app_service as svc
        from core.models import IntegrationToken
        _make_app(db_session)
        db_session.add(IntegrationToken(
            tenant_id="t1", provider="notion", access_token="plain-token", status="active",
        ))
        db_session.commit()

        seen = {}

        async def fake_dispatch(service, action, params, *, tenant_id, db):
            seen["service"] = service
            seen["action"] = action
            return {"ok": True, "data": {"pages": [{"title": "x"}]}, "backend": "native"}

        monkeypatch.setattr("core.mini_app_integration_dispatch.dispatch", fake_dispatch)
        out = await svc._inject_integration_sources(
            {"mcp_servers": [{"service": "notion", "action": "search", "params": {"q": "x"}}]},
            "t1", "w1", "ag1", db=db_session,
        )
        assert out["notion"] == {"pages": [{"title": "x"}]}
        assert seen["service"] == "notion"

    @pytest.mark.asyncio
    async def test_mcp_source_failure_skipped(self, monkeypatch):
        """A failing dispatch result is skipped (never crashes the run)."""
        import core.mini_app_service as svc

        async def fake_dispatch(service, action, params, *, tenant_id, db):
            return {"ok": False, "error": "failed"}
        monkeypatch.setattr("core.mini_app_integration_dispatch.dispatch", fake_dispatch)
        out = await svc._inject_integration_sources(
            {"mcp_servers": [{"service": "slack", "action": "send", "params": {}}]},
            "t1", "w1", "ag1",
        )
        assert out == {}

    @pytest.mark.asyncio
    async def test_run_injects_records_and_data_sources(self, db_session, canvas_fixture, monkeypatch):
        import core.mini_app_service as svc
        from core.mini_app_db_service import append_record
        from core.models import MiniApp
        app_id, canvas_id = canvas_fixture
        append_record(db_session, canvas_id, "t1", app_id, "todos", {"task": "pre"})
        app = db_session.query(MiniApp).filter(MiniApp.id == app_id).first()
        new_manifest = dict(app.manifest)
        new_manifest["db"] = {"enabled": True, "record_queries": ["todos"]}
        app.manifest = new_manifest
        db_session.commit()

        seen = {}

        class FakeRuntime:
            async def execute_python(self, code, *, policy=None, inputs=None, cwd=None, image=None, callback_handler=None, **kwargs):
                seen["records"] = inputs.get("records")
                seen["data_sources"] = inputs.get("data_sources")
                res = type("R", (), {
                    "success": True, "exit_code": 0, "stderr": "",
                    "stdout": "__MINIAPP_STATE__:" + json.dumps({"state": {}}),
                    "metadata": {},
                })()
                return res

        monkeypatch.setattr(svc, "get_miniapp_runtime", FakeRuntime)
        _patch_db(monkeypatch, db_session)
        result = await svc.run_stateful(canvas_id, user_id="u1", scopes=("*",))
        assert result["success"]
        assert seen["records"]["todos"][0]["data"]["task"] == "pre"
        assert seen["data_sources"] == {}


async def _boom():
    raise RuntimeError("boom")
