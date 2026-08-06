"""Mini-app DB store — agent-facing tools (mini_app_db_query / _write).

Exercises the registered actions through the action registry AND the agent
MCP dispatch seam (integrations.mcp_service.call_tool) exactly as an agent
would. Covers identity fail-closed, owner gating, tier floors, db_disabled.
"""
import uuid

import pytest

from core.action_registry import action_registry


@pytest.fixture
def patched_db(test_database, monkeypatch):
    """Bind core.database to a fresh temp-file DB for the duration of a test."""
    from sqlalchemy.orm import sessionmaker

    engine, _ = test_database
    SessionLocal = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=engine,
        expire_on_commit=False,
    )
    monkeypatch.setattr("core.database.SessionLocal", SessionLocal)
    monkeypatch.setattr("core.database.engine", engine)
    return engine, SessionLocal


def _ctx(user_id: str, tier: str = "autonomous", extra=None) -> dict:
    ctx = {"user_id": user_id, "agent_id": "agent-loop-1", "tier": tier}
    if extra:
        ctx.update(extra)
    return ctx


def _uid(prefix: str = "u") -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


def _make_instance(SessionLocal, owner_id: str, tier: str = "autonomous"):
    """Create a User row + published app + installed instance canvas in the DB."""
    from core.models import Canvas, CanvasLogic, CanvasState, MiniApp, User

    with SessionLocal() as s:
        user = User(
            id=owner_id, email=f"{owner_id}@test.dev", first_name="F", last_name="L",
            role="user", status="active",
        )
        s.add(user)
        s.flush()
        app_id = f"app-{uuid.uuid4().hex[:8]}"
        canvas_id = f"inst-{uuid.uuid4().hex[:8]}"
        s.add(MiniApp(
            id=app_id, tenant_id="t1", workspace_id="w1", created_by=owner_id,
            name="dbapp", version="1.0.0", status="published",
            manifest={
                "declared_scopes": ["*"], "mcp_servers": [], "dependencies": [],
                "base_image": "python:3.11-slim", "assets": [],
                "db": {"enabled": True},
                "initial_state": {}, "blueprint": {},
            },
            blueprint_canvas_id=f"src-{uuid.uuid4().hex[:8]}",
        ))
        s.add(Canvas(
            id=canvas_id, tenant_id="t1", created_by=owner_id, name="dbapp",
            canvas_type="mini_app", content={}, style={}, status="active",
            mini_app_id=app_id,
        ))
        s.add(CanvasState(canvas_id=canvas_id, tenant_id="t1", state={}, version=1))
        s.commit()
        return app_id, canvas_id


# ---------------------------------------------------------------------------
# mini_app_db_query
# ---------------------------------------------------------------------------
class TestDbQuery:
    @pytest.mark.asyncio
    async def test_owner_append_then_query(self, patched_db):
        SessionLocal = patched_db[1]
        owner = _uid("owner")
        app_id, canvas_id = _make_instance(SessionLocal, owner)

        w = await action_registry.execute_action(
            "mini_app_db_write",
            {"canvas_id": canvas_id, "op": "append", "series": "chart_data",
             "data": {"label": "Jan", "value": 12}},
            _ctx(owner),
        )
        assert w["success"] is True and w["ok"] is True and w["seq"] == 1

        q = await action_registry.execute_action(
            "mini_app_db_query",
            {"canvas_id": canvas_id, "op": "query", "series": "chart_data"},
            _ctx(owner),
        )
        assert q["success"] is True
        assert q["count"] == 1 and q["records"][0]["data"]["value"] == 12

        s = await action_registry.execute_action(
            "mini_app_db_query",
            {"canvas_id": canvas_id, "op": "list_series"},
            _ctx(owner),
        )
        assert [x["series"] for x in s["series"]] == ["chart_data"]

    @pytest.mark.asyncio
    async def test_non_owner_denied(self, patched_db):
        SessionLocal = patched_db[1]
        owner = _uid("owner")
        _, canvas_id = _make_instance(SessionLocal, owner)
        intruder = _uid("intruder")
        q = await action_registry.execute_action(
            "mini_app_db_query", {"canvas_id": canvas_id, "op": "query", "series": "s"},
            _ctx(intruder),
        )
        assert q["success"] is False
        assert "not owned" in q["error"]

    @pytest.mark.asyncio
    async def test_spoofed_user_id_ignored(self, patched_db):
        SessionLocal = patched_db[1]
        owner = _uid("owner")
        _, canvas_id = _make_instance(SessionLocal, owner)
        # args carry a foreign user_id — the handler must use context identity.
        q = await action_registry.execute_action(
            "mini_app_db_query",
            {"canvas_id": canvas_id, "op": "query", "series": "s", "user_id": owner},
            _ctx(_uid("real-owner-other")),
        )
        assert q["success"] is False

    @pytest.mark.asyncio
    async def test_student_tier_denied_intern_ok(self, patched_db):
        SessionLocal = patched_db[1]
        owner = _uid("owner")
        _, canvas_id = _make_instance(SessionLocal, owner)
        denied = await action_registry.execute_action(
            "mini_app_db_query", {"canvas_id": canvas_id, "op": "query", "series": "s"},
            _ctx(owner, tier="student"),
        )
        assert denied["success"] is False and "maturity tier" in denied["error"]
        ok = await action_registry.execute_action(
            "mini_app_db_query", {"canvas_id": canvas_id, "op": "query", "series": "s"},
            _ctx(owner, tier="intern"),
        )
        assert ok["success"] is True

    @pytest.mark.asyncio
    async def test_write_op_rejected_by_query_action(self, patched_db):
        SessionLocal = patched_db[1]
        owner = _uid("owner")
        _, canvas_id = _make_instance(SessionLocal, owner)
        r = await action_registry.execute_action(
            "mini_app_db_query",
            {"canvas_id": canvas_id, "op": "delete_series", "series": "s"},
            _ctx(owner),
        )
        assert r["success"] is False


# ---------------------------------------------------------------------------
# mini_app_db_write — tier floors
# ---------------------------------------------------------------------------
class TestDbWrite:
    @pytest.mark.asyncio
    async def test_supervised_ok_intern_denied(self, patched_db):
        SessionLocal = patched_db[1]
        owner = _uid("owner")
        _, canvas_id = _make_instance(SessionLocal, owner)
        denied = await action_registry.execute_action(
            "mini_app_db_write",
            {"canvas_id": canvas_id, "op": "append", "series": "s", "data": {"x": 1}},
            _ctx(owner, tier="intern"),
        )
        assert denied["success"] is False and "maturity tier" in denied["error"]
        ok = await action_registry.execute_action(
            "mini_app_db_write",
            {"canvas_id": canvas_id, "op": "append", "series": "s", "data": {"x": 1}},
            _ctx(owner, tier="supervised"),
        )
        assert ok["success"] is True

    @pytest.mark.asyncio
    async def test_unknown_tier_fails_closed(self, patched_db):
        SessionLocal = patched_db[1]
        owner = _uid("owner")
        _, canvas_id = _make_instance(SessionLocal, owner)
        r = await action_registry.execute_action(
            "mini_app_db_write",
            {"canvas_id": canvas_id, "op": "append", "series": "s", "data": {"x": 1}},
            _ctx(owner, tier="totally-bogus"),
        )
        assert r["success"] is False

    @pytest.mark.asyncio
    async def test_kill_switch_db_disabled(self, patched_db, monkeypatch):
        SessionLocal = patched_db[1]
        owner = _uid("owner")
        _, canvas_id = _make_instance(SessionLocal, owner)
        monkeypatch.setenv("ATOM_MINIAPP_DB_ENABLED", "false")
        import core.mini_app_db_service as dbsvc
        monkeypatch.setattr(dbsvc, "db_store_enabled", lambda: False)
        r = await action_registry.execute_action(
            "mini_app_db_query", {"canvas_id": canvas_id, "op": "query", "series": "s"},
            _ctx(owner),
        )
        assert r["success"] is False and r["error"] == "db_disabled"

    @pytest.mark.asyncio
    async def test_manifest_disabled_rejected(self, patched_db):
        SessionLocal = patched_db[1]
        owner = _uid("owner")
        app_id, canvas_id = _make_instance(SessionLocal, owner)
        from core.models import MiniApp

        with SessionLocal() as s:
            app = s.query(MiniApp).filter(MiniApp.id == app_id).first()
            manifest = dict(app.manifest)
            manifest["db"] = {"enabled": False}
            app.manifest = manifest
            s.commit()
        r = await action_registry.execute_action(
            "mini_app_db_write",
            {"canvas_id": canvas_id, "op": "append", "series": "s", "data": {"x": 1}},
            _ctx(owner),
        )
        assert r["success"] is False and r["error"] == "db_disabled"


# ---------------------------------------------------------------------------
# Agent MCP dispatch seam (the "chat with an agent" entry point)
# ---------------------------------------------------------------------------
class TestMCPDispatch:
    @pytest.mark.asyncio
    async def test_tools_exposed_to_agent_loop(self):
        from integrations.mcp_service import mcp_service

        tools = await mcp_service.get_all_tools()
        names = {t["name"] for t in tools}
        assert "mini_app_db_query" in names
        assert "mini_app_db_write" in names

    @pytest.mark.asyncio
    async def test_chat_agent_query_via_mcp_service(self, patched_db):
        from integrations.mcp_service import mcp_service

        SessionLocal = patched_db[1]
        owner = _uid("chat")
        app_id, canvas_id = _make_instance(SessionLocal, owner)
        with SessionLocal() as s:
            from core.mini_app_db_service import append_record

            append_record(s, canvas_id, "t1", app_id, "s", {"v": 1}, created_by=owner)
        res = await mcp_service.call_tool(
            "mini_app_db_query",
            {"canvas_id": canvas_id, "op": "query", "series": "s"},
            {"user_id": owner, "agent_id": "agent-loop-1", "tier": "autonomous"},
        )
        assert res["success"] is True and res["count"] == 1
