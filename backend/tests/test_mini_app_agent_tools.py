"""Mini-app authoring harness — agent-facing tools (agent-driven coding).

Exercises the registered ``mini_app_*`` actions (scaffold → write_logic →
dev_run → publish → install → run) exactly as an agent would via the action
registry. All Firecracker execution is mocked — no real VM.

DB strategy: the handlers use ``core.database.get_db_session()``; we point
``core.database.SessionLocal`` at a temp-file DB (``test_database``) so the
app code and our assertions share the same database.
"""
import uuid

import pytest

from core.action_registry import action_registry


@pytest.fixture
def patched_db(test_database, monkeypatch):
    """Bind core.database to a fresh temp-file DB for the duration of a test."""
    from sqlalchemy.orm import sessionmaker

    engine, _ = test_database
    # Mirror core.database's production sessionmaker (expire_on_commit=False)
    # so post-commit attribute access on committed instances works.
    SessionLocal = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=engine,
        expire_on_commit=False,
    )
    monkeypatch.setattr("core.database.SessionLocal", SessionLocal)
    monkeypatch.setattr("core.database.engine", engine)
    return engine, SessionLocal


def _ctx(user_id: str, extra=None) -> dict:
    ctx = {"user_id": user_id}
    if extra:
        ctx.update(extra)
    return ctx


def _uid(prefix: str = "u") -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


async def _scaffold(user_id: str, name: str = "Counter", deps=None, scopes=None):
    return await action_registry.execute_action(
        "mini_app_scaffold",
        {"name": name, "declared_scopes": scopes or ["canvas_render"], "dependencies": deps or []},
        _ctx(user_id),
    )


class _FakeResult:
    stdout = ""
    stderr = ""
    exit_code = 0
    truncated = False
    metadata = {"state_envelope": {"state": {"n": 1}, "storage_ops": []}}


class _FakeRuntime:
    async def execute_python(self, *a, **k):
        return _FakeResult()


@pytest.fixture
def patch_runtime(monkeypatch):
    """Patch the mini-app FC runtime + prepare_runtime gate for dev-run/publish."""
    monkeypatch.setattr("core.mini_app_service.prepare_runtime", lambda app, db: None)
    monkeypatch.setattr("core.mini_app_service.get_miniapp_runtime", lambda: _FakeRuntime())


# ---------------------------------------------------------------------------
# mini_app_scaffold
# ---------------------------------------------------------------------------
class TestAgentScaffold:
    @pytest.mark.asyncio
    async def test_creates_app_and_source_canvas(self, patched_db):
        from core.canvas_logic_service import CanvasLogicService
        from core.models import Canvas, MiniApp

        SessionLocal = patched_db[1]
        user_id = _uid()
        res = await _scaffold(user_id)
        assert res["success"] is True
        assert res["app_id"] and res["canvas_id"]
        assert res["logic_source"]

        with SessionLocal() as s:
            app = s.query(MiniApp).filter(MiniApp.id == res["app_id"]).first()
            assert app is not None
            assert app.created_by == user_id
            assert app.status == "draft"
            canvas = s.query(Canvas).filter(Canvas.id == res["canvas_id"]).first()
            assert canvas is not None
            assert canvas.canvas_type == "mini_app"
            assert canvas.mini_app_id == app.id
            logic = CanvasLogicService(s).load_logic(canvas.id)
            assert logic and logic.get("source")

    @pytest.mark.asyncio
    async def test_requires_name(self):
        res = await action_registry.execute_action("mini_app_scaffold", {}, _ctx(_uid()))
        assert res["success"] is False

    @pytest.mark.asyncio
    async def test_unauthenticated_fails_closed(self):
        res = await action_registry.execute_action("mini_app_scaffold", {"name": "X"}, {})
        assert res["success"] is False


# ---------------------------------------------------------------------------
# mini_app_write_logic — syntax gate + owner
# ---------------------------------------------------------------------------
class TestAgentWriteLogic:
    @pytest.mark.asyncio
    async def test_saves_valid_logic(self, patched_db):
        from core.canvas_logic_service import CanvasLogicService

        SessionLocal = patched_db[1]
        user_id = _uid()
        sc = await _scaffold(user_id)
        src = "state = {**state, 'n': state.get('n', 0) + 1}\n"
        res = await action_registry.execute_action(
            "mini_app_write_logic", {"app_id": sc["app_id"], "source": src}, _ctx(user_id)
        )
        assert res["success"] is True
        with SessionLocal() as s:
            saved = CanvasLogicService(s).load_logic(sc["canvas_id"])
        assert saved and "state.get('n', 0) + 1" in saved["source"]

    @pytest.mark.asyncio
    async def test_rejects_syntax_error(self, patched_db):
        user_id = _uid()
        sc = await _scaffold(user_id)
        res = await action_registry.execute_action(
            "mini_app_write_logic", {"app_id": sc["app_id"], "source": "def broken(:"}, _ctx(user_id)
        )
        assert res["success"] is False
        assert "SyntaxError" in res["error"]

    @pytest.mark.asyncio
    async def test_rejects_non_owner(self, patched_db):
        owner = _uid()
        sc = await _scaffold(owner)
        res = await action_registry.execute_action(
            "mini_app_write_logic", {"app_id": sc["app_id"], "source": "x = 1"}, _ctx(_uid())
        )
        assert res["success"] is False
        assert "owner" in res["error"].lower()


# ---------------------------------------------------------------------------
# mini_app_dev_run — dry, no commit
# ---------------------------------------------------------------------------
class TestAgentDevRun:
    @pytest.mark.asyncio
    async def test_dev_run_returns_state_no_commit(self, patched_db, patch_runtime):
        from core.models import CanvasState

        SessionLocal = patched_db[1]
        user_id = _uid()
        sc = await _scaffold(user_id)
        res = await action_registry.execute_action(
            "mini_app_dev_run", {"app_id": sc["app_id"], "inputs": {}}, _ctx(user_id)
        )
        assert res["success"] is True
        assert res["state"] == {"n": 1}
        with SessionLocal() as s:
            rows = s.query(CanvasState).filter(CanvasState.canvas_id == sc["canvas_id"]).all()
        assert rows == []

    @pytest.mark.asyncio
    async def test_dev_run_requires_owner(self, patched_db, patch_runtime):
        owner = _uid()
        sc = await _scaffold(owner)
        res = await action_registry.execute_action(
            "mini_app_dev_run", {"app_id": sc["app_id"]}, _ctx(_uid())
        )
        assert res["success"] is False
        assert "owner" in res["error"].lower()


# ---------------------------------------------------------------------------
# mini_app_publish + mini_app_install — the release loop
# ---------------------------------------------------------------------------
class TestAgentPublishInstall:
    @pytest.mark.asyncio
    async def test_publish_then_install(self, patched_db, patch_runtime):
        from core.models import Canvas, MiniApp

        SessionLocal = patched_db[1]
        user_id = _uid()
        sc = await _scaffold(user_id)
        app_id = sc["app_id"]

        pub = await action_registry.execute_action("mini_app_publish", {"app_id": app_id}, _ctx(user_id))
        assert pub["success"] is True
        with SessionLocal() as s:
            app = s.query(MiniApp).filter(MiniApp.id == app_id).first()
            assert app.status == "published"
            assert (app.manifest or {}).get("blueprint")

        inst = await action_registry.execute_action("mini_app_install", {"app_id": app_id}, _ctx(user_id))
        assert inst["success"] is True
        assert inst["canvas_id"] and inst["canvas_id"] != sc["canvas_id"]
        with SessionLocal() as s:
            instance = s.query(Canvas).filter(Canvas.id == inst["canvas_id"]).first()
            assert instance is not None
            assert instance.mini_app_id == app_id
            assert instance.created_by == user_id

    @pytest.mark.asyncio
    async def test_install_requires_published(self, patched_db, patch_runtime):
        user_id = _uid()
        sc = await _scaffold(user_id)
        res = await action_registry.execute_action(
            "mini_app_install", {"app_id": sc["app_id"]}, _ctx(user_id)
        )
        assert res["success"] is False
        assert "published" in res["error"].lower()


# ---------------------------------------------------------------------------
# mini_app_list + mini_app_get_state
# ---------------------------------------------------------------------------
class TestAgentReads:
    @pytest.mark.asyncio
    async def test_list_returns_owned_apps(self, patched_db):
        user_id = _uid()
        await _scaffold(user_id, name="A")
        await _scaffold(user_id, name="B")
        res = await action_registry.execute_action("mini_app_list", {}, _ctx(user_id))
        assert res["success"] is True
        names = {a["name"] for a in res["apps"]}
        assert {"A", "B"}.issubset(names)

    @pytest.mark.asyncio
    async def test_get_state_empty_before_any_run(self, patched_db):
        user_id = _uid()
        sc = await _scaffold(user_id)
        res = await action_registry.execute_action(
            "mini_app_get_state", {"canvas_id": sc["canvas_id"]}, _ctx(user_id)
        )
        assert res["success"] is True
        assert res["version"] == 0


# ---------------------------------------------------------------------------
# mini_app_run — stateful run of an installed instance
# ---------------------------------------------------------------------------
class TestAgentRun:
    @pytest.mark.asyncio
    async def test_run_persists_state_and_versions(self, patched_db, patch_runtime):
        from core.models import CanvasState

        SessionLocal = patched_db[1]
        user_id = _uid()
        sc = await _scaffold(user_id)
        app_id = sc["app_id"]
        await action_registry.execute_action("mini_app_publish", {"app_id": app_id}, _ctx(user_id))
        inst = await action_registry.execute_action("mini_app_install", {"app_id": app_id}, _ctx(user_id))
        canvas_id = inst["canvas_id"]

        res = await action_registry.execute_action(
            "mini_app_run", {"canvas_id": canvas_id, "inputs": {}}, _ctx(user_id)
        )
        assert res["success"] is True
        # install() seeds CanvasState at version 1; the first stateful run bumps it.
        assert res["version"] == 2
        with SessionLocal() as s:
            row = s.query(CanvasState).filter(CanvasState.canvas_id == canvas_id).first()
            assert row is not None
            assert row.state == {"n": 1}
            assert row.version == 2

    @pytest.mark.asyncio
    async def test_run_requires_authenticated_user(self, patch_runtime):
        res = await action_registry.execute_action("mini_app_run", {"canvas_id": "x"}, {})
        assert res["success"] is False


# ---------------------------------------------------------------------------
# Agent harness — acceptance tests, logic checkpoints, constraint probe
# ---------------------------------------------------------------------------
class TestAgentHarness:
    @pytest.mark.asyncio
    async def test_set_tests_persists_and_validates(self, patched_db):
        SessionLocal = patched_db[1]
        user_id = _uid()
        sc = await _scaffold(user_id)
        tests = [
            {
                "name": "first increment",
                "initial_state": {"n": 0},
                "inputs": {},
                "expect_state": {"n": 1},
            },
            {"name": "op case", "expect_ops": [{"op": "put", "key": "out.txt"}]},
        ]
        res = await action_registry.execute_action(
            "mini_app_set_tests", {"app_id": sc["app_id"], "tests": tests}, _ctx(user_id)
        )
        assert res["success"] is True
        assert res["tests"] == 2
        with SessionLocal() as s:
            from core.models import MiniApp

            app = s.query(MiniApp).filter(MiniApp.id == sc["app_id"]).first()
            assert (app.manifest or {}).get("tests") == tests

    @pytest.mark.asyncio
    async def test_set_tests_rejects_case_without_assertions(self, patched_db):
        user_id = _uid()
        sc = await _scaffold(user_id)
        res = await action_registry.execute_action(
            "mini_app_set_tests",
            {"app_id": sc["app_id"], "tests": [{"inputs": {}}]},
            _ctx(user_id),
        )
        assert res["success"] is False
        assert "expect_state" in res["error"] or "expect_ops" in res["error"]

    @pytest.mark.asyncio
    async def test_set_tests_requires_owner(self, patched_db):
        owner = _uid()
        sc = await _scaffold(owner)
        res = await action_registry.execute_action(
            "mini_app_set_tests",
            {"app_id": sc["app_id"], "tests": [{"expect_state": {}}]},
            _ctx(_uid()),
        )
        assert res["success"] is False
        assert "owner" in res["error"].lower()

    @pytest.mark.asyncio
    async def test_run_tests_passes_and_reports_diff(self, patched_db, patch_runtime):
        from core.models import CanvasState

        SessionLocal = patched_db[1]
        user_id = _uid()
        sc = await _scaffold(user_id)
        passing = [{"name": "matches fake", "expect_state": {"n": 1}}]
        failing = [{"name": "wants more", "expect_state": {"n": 2}}]
        await action_registry.execute_action(
            "mini_app_set_tests", {"app_id": sc["app_id"], "tests": passing}, _ctx(user_id)
        )
        res = await action_registry.execute_action(
            "mini_app_run_tests", {"app_id": sc["app_id"]}, _ctx(user_id)
        )
        assert res["success"] is True
        assert res["passed"] == 1 and res["total"] == 1 and res["all_passed"] is True
        assert res["results"][0]["passed"] is True

        await action_registry.execute_action(
            "mini_app_set_tests", {"app_id": sc["app_id"], "tests": failing}, _ctx(user_id)
        )
        res = await action_registry.execute_action(
            "mini_app_run_tests", {"app_id": sc["app_id"]}, _ctx(user_id)
        )
        assert res["passed"] == 0 and res["all_passed"] is False
        entry = res["results"][0]
        assert entry["passed"] is False
        assert entry["diff"] == {"n": {"expected": 2, "actual": 1}}

        # dry-run: no CanvasState committed for the blueprint canvas
        with SessionLocal() as s:
            rows = s.query(CanvasState).filter(CanvasState.canvas_id == sc["canvas_id"]).all()
        assert rows == []

    @pytest.mark.asyncio
    async def test_run_tests_requires_saved_tests(self, patched_db, patch_runtime):
        user_id = _uid()
        sc = await _scaffold(user_id)
        res = await action_registry.execute_action(
            "mini_app_run_tests", {"app_id": sc["app_id"]}, _ctx(user_id)
        )
        assert res["success"] is True
        assert res["total"] == 0

    @pytest.mark.asyncio
    async def test_write_logic_checkpoints_and_history(self, patched_db):
        user_id = _uid()
        sc = await _scaffold(user_id)
        v1 = "state = dict(state)\nstate['a'] = 1\n"
        v2 = "state = dict(state)\nstate['b'] = 2\n"
        r1 = await action_registry.execute_action(
            "mini_app_write_logic", {"app_id": sc["app_id"], "source": v1}, _ctx(user_id)
        )
        assert r1["success"] is True and r1["version"] == 1
        r2 = await action_registry.execute_action(
            "mini_app_write_logic", {"app_id": sc["app_id"], "source": v2}, _ctx(user_id)
        )
        assert r2["success"] is True and r2["version"] == 2
        hist = await action_registry.execute_action(
            "mini_app_logic_history", {"app_id": sc["app_id"]}, _ctx(user_id)
        )
        assert hist["success"] is True
        versions = [h["version"] for h in hist["history"]]
        assert versions == [1, 2]
        assert "state['a']" in hist["history"][0]["preview"]

    @pytest.mark.asyncio
    async def test_revert_logic_restores_previous_version(self, patched_db):
        from core.canvas_logic_service import CanvasLogicService

        SessionLocal = patched_db[1]
        user_id = _uid()
        sc = await _scaffold(user_id)
        v1 = "state = dict(state)\nstate['a'] = 1\n"
        v2 = "state = dict(state)\nstate['b'] = 2\n"
        await action_registry.execute_action(
            "mini_app_write_logic", {"app_id": sc["app_id"], "source": v1}, _ctx(user_id)
        )
        await action_registry.execute_action(
            "mini_app_write_logic", {"app_id": sc["app_id"], "source": v2}, _ctx(user_id)
        )
        rev = await action_registry.execute_action(
            "mini_app_revert_logic",
            {"app_id": sc["app_id"], "version": 1},
            _ctx(user_id),
        )
        assert rev["success"] is True
        with SessionLocal() as s:
            saved = CanvasLogicService(s).load_logic(sc["canvas_id"])
        assert saved and "state['a']" in saved["source"]
        hist = await action_registry.execute_action(
            "mini_app_logic_history", {"app_id": sc["app_id"]}, _ctx(user_id)
        )
        # revert itself is checkpointed as a new version
        assert [h["version"] for h in hist["history"]] == [1, 2, 3]

    @pytest.mark.asyncio
    async def test_revert_logic_missing_version(self, patched_db):
        user_id = _uid()
        sc = await _scaffold(user_id)
        await action_registry.execute_action(
            "mini_app_write_logic",
            {"app_id": sc["app_id"], "source": "state = dict(state)\n"},
            _ctx(user_id),
        )
        res = await action_registry.execute_action(
            "mini_app_revert_logic",
            {"app_id": sc["app_id"], "version": 99},
            _ctx(user_id),
        )
        assert res["success"] is False
        assert "not found" in res["error"]

    @pytest.mark.asyncio
    async def test_status_probe_surfaces_constraints(self, patched_db, monkeypatch):
        user_id = _uid()
        sc = await _scaffold(user_id)
        monkeypatch.setattr(
            "core.mini_app_runtime.get_miniapp_runtime",
            lambda: None,
        )
        res = await action_registry.execute_action(
            "mini_app_status", {"app_id": sc["app_id"]}, _ctx(user_id)
        )
        assert res["success"] is True
        st = res["status"]
        assert st["app_id"] == sc["app_id"]
        assert st["status"] == "draft"
        assert st["logic"]["present"] is True
        assert st["logic"]["syntax_ok"] is True
        assert isinstance(st["scopes"]["effective"], list)
        assert st["dependencies"]["count"] == 0
        assert st["rootfs"] is None
        assert st["runtime"]["available"] is True
        assert st["tests"]["count"] == 0


# ---------------------------------------------------------------------------
# Agent-chat dispatch path — the "chat with an agent in the main chat UI" entry
# point. The agent loop calls integrations.mcp_service.call_tool with a context
# dict carrying user_id + agent_id; this test exercises that exact seam (not
# action_registry directly) so a mini-app can be created from chat.
# ---------------------------------------------------------------------------
class TestAgentChatDispatch:
    @pytest.mark.asyncio
    async def test_chat_agent_scaffolds_via_mcp_service(self, patched_db):
        from core.models import MiniApp

        from integrations.mcp_service import mcp_service

        SessionLocal = patched_db[1]
        user_id = _uid("chat")
        # Context shape the agent loop supplies on every tool call.
        context = {"user_id": user_id, "agent_id": "agent-loop-1", "tier": "autonomous"}
        res = await mcp_service.call_tool(
            "mini_app_scaffold",
            {"name": "ChatCounter", "declared_scopes": ["canvas_render"]},
            context,
        )
        assert res["success"] is True
        assert res["app_id"]
        with SessionLocal() as s:
            app = s.query(MiniApp).filter(MiniApp.id == res["app_id"]).first()
            assert app is not None
            assert app.created_by == user_id
            assert app.status == "draft"

    @pytest.mark.asyncio
    async def test_chat_agent_missing_user_id_fails_closed(self, patched_db):
        from integrations.mcp_service import mcp_service

        res = await mcp_service.call_tool(
            "mini_app_scaffold",
            {"name": "NoIdentity"},
            {"agent_id": "agent-loop-1"},  # no user_id → authoring must fail closed
        )
        assert res["success"] is False
        assert "Authenticated user" in res["error"]

    @pytest.mark.asyncio
    async def test_tools_exposed_to_agent_loop(self):
        from integrations.mcp_service import mcp_service

        tools = await mcp_service.get_all_tools()
        names = {t["name"] for t in tools}
        for required in (
            "mini_app_scaffold",
            "mini_app_write_logic",
            "mini_app_dev_run",
            "mini_app_run_tests",
            "mini_app_publish",
            "mini_app_install",
            "mini_app_run",
        ):
            assert required in names, f"{required} not exposed to the agent loop"
