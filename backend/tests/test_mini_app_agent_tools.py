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


async def _scaffold(
    user_id: str,
    name: str = "Counter",
    deps=None,
    scopes=None,
    *,
    tenant: str = "default",
    workspace=None,
):
    # Seed the authoritative actor first: scaffold/run resolve the acting user
    # from the User row (a bare context user_id is not an actor), and the
    # canvas audit row scaffold writes is what the run gate reads back.
    from core.database import get_db_session
    from tests.mini_app_authority_fixtures import ensure_actor

    with get_db_session() as db:
        ensure_actor(db, user_id, tenant, workspace)
        db.commit()
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
    monkeypatch.setattr(
        "core.mini_app_service.prepare_runtime",
        lambda app, db, commit=True: None)
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
        # The harness DevRunResult reads state_changed/version to render the
        # run summary ("exit code · state_changed") — the handler must pass them
        # through from run_stateful (regression for the always-false display).
        assert res["state_changed"] is True
        assert res["version"] == 0
        assert res["proposed_ops"] == []
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
        from core.models import MiniApp

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
        with SessionLocal() as s:
            app = s.query(MiniApp).filter(MiniApp.id == sc["app_id"]).first()
            assert app is not None
            manifest_before = dict(app.manifest or {})
        res = await action_registry.execute_action(
            "mini_app_set_tests", {"app_id": sc["app_id"], "tests": tests}, _ctx(user_id)
        )
        assert res["success"] is True
        assert res["tests"] == 2
        with SessionLocal() as s:
            app = s.query(MiniApp).filter(MiniApp.id == sc["app_id"]).first()
            assert app is not None
            assert app.manifest == {**manifest_before, "tests": tests}

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


@pytest.mark.asyncio
async def test_acceptance_distinguishes_missing_null_and_empty_assertions(monkeypatch):
    from unittest.mock import AsyncMock

    from core.mini_app_service import run_tests, validate_tests

    empty = {"expect_state": {}, "expect_ops": []}
    with pytest.raises(ValueError, match="expect_state"):
        validate_tests([empty])

    guest = AsyncMock(side_effect=[
        {"success": True, "state": {}},
        {"success": True, "state": {"reviewed_at": None}},
    ])
    monkeypatch.setattr("core.mini_app_service.run_stateful", guest)
    expect_null = {"expect_state": {"reviewed_at": None}}

    report = await run_tests("app", "canvas", [empty, expect_null, expect_null])

    assert report["passed"] == 1
    assert report["results"][0]["passed"] is False
    assert report["results"][1]["diff"]["reviewed_at"] == {
        "expected": None, "actual": None, "missing": True,
    }
    assert report["results"][2]["passed"] is True
    assert guest.await_count == 2


class _ControllerFailureResult:
    truncated = False

    def __init__(self, controller_error, *, exit_code=1, state=None):
        self.stdout = "secret stdout"
        self.stderr = "secret stderr"
        self.exit_code = exit_code
        self.metadata = {
            "controller_error": controller_error,
            "unrelated": "must not leak",
        }
        if state is not None:
            self.metadata["state_envelope"] = {"state": state, "storage_ops": []}


class _ControllerFailureRuntime:
    def __init__(self, result):
        self.result = result

    async def execute_python(self, *args, **kwargs):
        return self.result


@pytest.mark.asyncio
async def test_run_stateful_nonzero_projects_only_valid_controller_error(
    patched_db, monkeypatch
):
    from core.mini_app_service import run_stateful

    user_id = _uid()
    sc = await _scaffold(user_id)
    for controller_error in (
        "UnboundLocalError", "NameError", "TypeError", "KeyError",
        "IndexError", "ValueError", "ZeroDivisionError",
    ):
        runtime = _ControllerFailureRuntime(
            _ControllerFailureResult(controller_error))
        monkeypatch.setattr(
            "core.mini_app_service.get_miniapp_runtime", lambda runtime=runtime: runtime)
        res = await run_stateful(sc["canvas_id"], user_id=user_id, persist=False)

        assert res["success"] is False
        assert res["controller_error"] == controller_error
        assert res["stdout"] == "secret stdout"
        assert "unrelated" not in res


@pytest.mark.asyncio
@pytest.mark.parametrize("controller_error", [
    None, "", "RuntimeError", "KeyError: boom", "SystemExit", 5,
])
async def test_run_stateful_nonzero_drops_invalid_controller_error(
    patched_db, monkeypatch, controller_error
):
    from core.mini_app_service import run_stateful

    user_id = _uid()
    sc = await _scaffold(user_id)
    runtime = _ControllerFailureRuntime(
        _ControllerFailureResult(controller_error))
    monkeypatch.setattr("core.mini_app_service.get_miniapp_runtime", lambda: runtime)

    res = await run_stateful(sc["canvas_id"], user_id=user_id, persist=False)

    assert res["success"] is False
    assert "controller_error" not in res


@pytest.mark.asyncio
async def test_run_stateful_success_does_not_project_controller_error(
    patched_db, monkeypatch
):
    from core.mini_app_service import run_stateful

    user_id = _uid()
    sc = await _scaffold(user_id)
    runtime = _ControllerFailureRuntime(
        _ControllerFailureResult("KeyError", exit_code=0, state={"n": 1}))
    monkeypatch.setattr("core.mini_app_service.get_miniapp_runtime", lambda: runtime)

    res = await run_stateful(sc["canvas_id"], user_id=user_id, persist=False)

    assert res["success"] is True
    assert "controller_error" not in res


@pytest.mark.asyncio
async def test_acceptance_failed_row_projects_only_valid_controller_error(monkeypatch):
    from unittest.mock import AsyncMock

    from core.mini_app_service import run_tests

    for controller_error in (
        "UnboundLocalError", "NameError", "TypeError", "KeyError",
        "IndexError", "ValueError", "ZeroDivisionError",
    ):
        guest = AsyncMock(return_value={
            "success": False,
            "error": "raw runtime text",
            "controller_error": controller_error,
            "stdout": "secret stdout",
            "stderr": "secret stderr",
            "inputs": {"secret": 1},
            "unrelated": "must not leak",
        })
        monkeypatch.setattr("core.mini_app_service.run_stateful", guest)

        report = await run_tests(
            "app", "canvas", [{"name": "typed", "expect_state": {"n": 1}}])

        assert report["results"][0] == {
            "name": "typed",
            "passed": False,
            "error": "raw runtime text",
            "controller_error": controller_error,
        }


@pytest.mark.asyncio
@pytest.mark.parametrize("controller_error", [
    None, "", "RuntimeError", "KeyError: boom", "SystemExit", 5,
])
async def test_acceptance_failed_row_drops_invalid_controller_error(
    monkeypatch, controller_error
):
    from unittest.mock import AsyncMock

    from core.mini_app_service import run_tests

    guest = AsyncMock(return_value={
        "success": False,
        "error": "raw runtime text",
        "controller_error": controller_error,
        "stdout": "secret stdout",
    })
    monkeypatch.setattr("core.mini_app_service.run_stateful", guest)

    report = await run_tests(
        "app", "canvas", [{"name": "typed", "expect_state": {"n": 1}}])

    assert report["results"][0] == {
        "name": "typed",
        "passed": False,
        "error": "raw runtime text",
    }


@pytest.mark.asyncio
async def test_acceptance_checks_saved_case_digest_before_run(patched_db, monkeypatch):
    from unittest.mock import AsyncMock

    from core.task_lifecycle import _approval_payload_hash
    from tools.mini_app_tool import mini_app_run_tests, mini_app_set_tests

    actor_id = _uid()
    draft = await _scaffold(actor_id)
    context = _ctx(actor_id)
    app_id = draft["app_id"]
    original = [{"expect_state": {"total": 27}}]
    changed = [{"expect_state": {"total": 0}}]
    assert (await mini_app_set_tests({"app_id": app_id, "tests": changed}, context))["success"]
    run = AsyncMock(return_value={"passed": 1, "total": 1, "results": []})
    monkeypatch.setattr("core.mini_app_service.run_tests", run)

    mismatch = await mini_app_run_tests({
        "app_id": app_id, "expected_tests_sha256": _approval_payload_hash(original),
    }, context)
    assert mismatch["error"] == "mini_app_acceptance_tests_changed"
    run.assert_not_awaited()

    digest = _approval_payload_hash(changed)
    result = await mini_app_run_tests({
        "app_id": app_id, "expected_tests_sha256": digest,
    }, context)
    assert result["success"] and result["tests_sha256"] == digest
    assert run.await_args.args[2] == changed


@pytest.mark.asyncio
async def test_acceptance_stops_after_concurrent_draft_edit(patched_db, patch_runtime, monkeypatch):
    from unittest.mock import AsyncMock

    from tools.mini_app_tool import mini_app_run_tests, mini_app_set_tests, mini_app_write_logic

    actor_id = _uid()
    app_id = (await _scaffold(actor_id))["app_id"]
    context = _ctx(actor_id)
    original = await mini_app_write_logic({"app_id": app_id, "source": "state = {'n': 1}"}, context)
    assert original["success"]
    cases = [{"name": name, "expect_state": {"n": 1}} for name in ("first", "second")]
    assert (await mini_app_set_tests({"app_id": app_id, "tests": cases}, context))["success"]

    async def execute_first(*args, **kwargs):
        updated = await mini_app_write_logic({"app_id": app_id, "source": "state = {'n': 2}"}, context)
        assert updated["success"]
        return _FakeResult()

    execute = AsyncMock(side_effect=execute_first)
    runtime = _FakeRuntime()
    runtime.execute_python = execute
    monkeypatch.setattr("core.mini_app_service.get_miniapp_runtime", lambda: runtime)

    report = await mini_app_run_tests({
        "app_id": app_id, "expected_source_sha256": original["source_sha256"],
    }, context)
    assert report == {"success": False, "error": "mini_app_logic_changed"}
    execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_acceptance_repair_cannot_overwrite_newer_saved_logic(patched_db):
    from core.canvas_logic_service import CanvasLogicService
    from core.database import get_db_session
    from tools.mini_app_tool import mini_app_write_logic

    actor_id = _uid()
    draft = await _scaffold(actor_id)
    app_id = draft["app_id"]
    context = _ctx(actor_id)

    first = await mini_app_write_logic({"app_id": app_id, "source": "state = {'n': 1}"}, context)
    peer_source = "state = {'n': 2}"
    peer = await mini_app_write_logic({"app_id": app_id, "source": peer_source}, context)
    assert first["success"] and peer["success"]

    repair = await mini_app_write_logic({
        "app_id": app_id, "source": "state = {'n': 3}",
        "expected_source_sha256": first["source_sha256"],
    }, context)
    assert not repair["success"] and repair["error"] == "mini_app_logic_changed"
    with get_db_session() as db:
        assert CanvasLogicService(db).load_logic(draft["canvas_id"])["source"] == peer_source


@pytest.mark.asyncio
async def test_owner_case_editor_preserves_newer_suite(patched_db):
    owner = _uid()
    app_id = (await _scaffold(owner))["app_id"]
    async def call(action, args, actor=owner):
        return await action_registry.execute_action(action, {"app_id": app_id, **args}, _ctx(actor))

    read = {"include_acceptance_cases": True}
    status = (await call("mini_app_status", read))["status"]
    loaded = status["acceptance"]
    from core.mini_app_service import logic_source_sha256
    from core.models import CanvasLogic, MiniApp

    with patched_db[1]() as db:
        canvas_id = db.get(MiniApp, app_id).blueprint_canvas_id
        logic = db.query(CanvasLogic).filter_by(canvas_id=canvas_id).one()
        assert status["logic"]["source_sha256"] == logic_source_sha256(logic.source)
    assert loaded["cases"] == []
    assert not (await call("mini_app_status", read, _uid()))["success"]
    first = [{"name": "initial", "expect_state": {"total": 7}}]
    saved = await call("mini_app_set_tests", {"tests": first,
                                             "expected_tests_sha256": loaded["tests_sha256"]})
    assert saved["success"]
    assert saved["tests_sha256"] != loaded["tests_sha256"]
    rejected = await call("mini_app_set_tests", {"tests": [{"expect_state": {"total": 8}}],
                                                "expected_tests_sha256": loaded["tests_sha256"]})
    assert rejected["error"] == "mini_app_acceptance_tests_changed"
    refreshed = (await call("mini_app_status", read))["status"]["acceptance"]
    assert refreshed == {"cases": first, "tests_sha256": saved["tests_sha256"]}


@pytest.mark.asyncio
async def test_owner_case_editor_rejects_invalid_existing_suite(patched_db):
    from core.models import MiniApp
    from core.task_lifecycle import _approval_payload_hash

    owner = _uid()
    app_id = (await _scaffold(owner))["app_id"]
    with patched_db[1]() as db:
        app = db.get(MiniApp, app_id)
        app.manifest = {**app.manifest, "tests": {"legacy": "invalid"}}
        db.commit()

    loaded = await action_registry.execute_action(
        "mini_app_status", {"app_id": app_id, "include_acceptance_cases": True}, _ctx(owner)
    )
    assert loaded["error"] == "mini_app_saved_tests_invalid"
    saved = await action_registry.execute_action(
        "mini_app_set_tests",
        {"app_id": app_id, "tests": [{"expect_state": {"total": 7}}],
         "expected_tests_sha256": _approval_payload_hash([])}, _ctx(owner),
    )
    assert saved["error"] == "mini_app_saved_tests_invalid"
    with patched_db[1]() as db:
        assert db.get(MiniApp, app_id).manifest["tests"] == {"legacy": "invalid"}


# ---------------------------------------------------------------------------
# Durable Canvas grading — RPC admission/status + worker integration.
# Store fencing/recovery is covered by the separately tested store module.
# ---------------------------------------------------------------------------
@pytest.fixture
def grade_table(patched_db):
    from core.canvas_grade_runs import CanvasGradeRun

    CanvasGradeRun.__table__.create(bind=patched_db[0], checkfirst=True)
    return patched_db


@pytest.mark.asyncio
async def test_grade_rpc_auth_same_uuid_digest_worker_and_exact_miss(
    grade_table, monkeypatch
):
    """One controlled RPC/worker integration path; the store is tested elsewhere."""
    from unittest.mock import AsyncMock

    from core.canvas_grade_runs import CanvasGradeRun
    from core.canvas_grade_worker import process_pending_grades_once
    from core.task_lifecycle import _approval_payload_hash
    from tools.mini_app_tool import mini_app_write_logic

    owner = _uid("grade")
    scope_tenant = f"tenant-{uuid.uuid4().hex[:8]}"
    scope_workspace = f"workspace-{uuid.uuid4().hex[:8]}"
    app_id = (await _scaffold(
        owner, tenant=scope_tenant, workspace=scope_workspace))["app_id"]
    context = _ctx(owner)
    from core.models import MiniApp, User

    with grade_table[1]() as db:
        user = db.get(User, owner)
        app = db.get(MiniApp, app_id)
        assert user.tenant_id == app.tenant_id == scope_tenant
        assert user.workspace_id == app.workspace_id == scope_workspace
    cases = [{"name": "one", "expect_state": {"n": 1}}]
    assert (await action_registry.execute_action(
        "mini_app_set_tests", {"app_id": app_id, "tests": cases}, context
    ))["success"]
    logic = await mini_app_write_logic(
        {"app_id": app_id, "source": "state = {'n': 1}"}, context)
    source_digest = logic["source_sha256"]
    tests_digest = _approval_payload_hash(cases)
    submission = str(uuid.uuid4())

    # Authentication is required before admission or status reads.
    denied = await action_registry.execute_action(
        "mini_app_start_grade",
        {"app_id": app_id, "submission_id": submission,
         "expected_source_digest": source_digest,
         "expected_tests_digest": tests_digest},
        {},
    )
    assert denied["status"] == "forbidden"

    # Source/tests pins use the same stable codes as the Chat harness.
    stale_source = await action_registry.execute_action(
        "mini_app_start_grade",
        {"app_id": app_id, "submission_id": str(uuid.uuid4()),
         "expected_source_digest": "stale",
         "expected_tests_digest": tests_digest},
        context,
    )
    assert stale_source["error"] == "mini_app_logic_changed"
    stale_tests = await action_registry.execute_action(
        "mini_app_start_grade",
        {"app_id": app_id, "submission_id": str(uuid.uuid4()),
         "expected_source_digest": source_digest,
         "expected_tests_digest": "stale"},
        context,
    )
    assert stale_tests["error"] == "mini_app_acceptance_tests_changed"

    started = await action_registry.execute_action(
        "mini_app_start_grade",
        {"app_id": app_id, "submission_id": submission,
         "expected_source_digest": source_digest,
         "expected_tests_digest": tests_digest},
        context,
    )
    assert started["status"] == "pending" and started["run_id"]
    run_id = started["run_id"]

    # Same UUID + same pins is idempotent; divergent pins conflict.
    retried = await action_registry.execute_action(
        "mini_app_start_grade",
        {"app_id": app_id, "submission_id": submission,
         "expected_source_digest": source_digest,
         "expected_tests_digest": tests_digest},
        context,
    )
    assert retried["run_id"] == run_id and retried["status"] == "pending"
    conflict = await action_registry.execute_action(
        "mini_app_start_grade",
        {"app_id": app_id, "submission_id": submission,
         "expected_source_digest": "different",
         "expected_tests_digest": tests_digest},
        context,
    )
    assert conflict["status"] == "conflict"

    # The worker executes and persists the exact grading report.
    report = {"passed": 1, "total": 1, "results": [{"passed": True}]}
    run_tests = AsyncMock(return_value=report)
    monkeypatch.setattr("core.mini_app_service.run_tests", run_tests)
    assert await process_pending_grades_once(limit=1) == 1
    run_tests.assert_awaited_once()
    with grade_table[1]() as db:
        row = db.get(CanvasGradeRun, run_id)
        assert row.status == "completed" and row.report == report

    completed = await action_registry.execute_action(
        "mini_app_grade_status",
        {"app_id": app_id, "submission_id": submission}, context,
    )
    assert completed["status"] == "completed" and completed["report"] == report

    # Exact authorized miss is Python None (signed RPC data null). A foreign
    # actor still gets a typed failure, never a silent miss.
    miss = await action_registry.execute_action(
        "mini_app_grade_status",
        {"app_id": app_id, "run_id": str(uuid.uuid4())}, context,
    )
    assert miss is None

    other = _uid("other")
    from core.database import get_db_session
    from tests.mini_app_authority_fixtures import ensure_actor

    with get_db_session() as db:
        ensure_actor(db, other, scope_tenant, scope_workspace)
        db.commit()
    foreign = await action_registry.execute_action(
        "mini_app_grade_status",
        {"app_id": app_id, "run_id": run_id}, _ctx(other),
    )
    assert foreign["status"] == "forbidden"


@pytest.mark.asyncio
async def test_grade_rpc_absent_scope_refuses_without_write(grade_table):
    """The durable store requires a non-null workspace; refusal is pre-write."""
    from core.canvas_grade_runs import CanvasGradeRun

    owner = _uid("noscope")
    app_id = (await _scaffold(
        owner, tenant="tenant-noscope", workspace=None))["app_id"]
    context = _ctx(owner)
    submission = str(uuid.uuid4())

    started = await action_registry.execute_action(
        "mini_app_start_grade",
        {"app_id": app_id, "submission_id": submission,
         "expected_source_digest": "source", "expected_tests_digest": "tests"},
        context,
    )
    assert started["status"] == "forbidden"
    assert started["error"] == "scope_mismatch"

    status = await action_registry.execute_action(
        "mini_app_grade_status",
        {"app_id": app_id, "submission_id": submission}, context,
    )
    assert status["status"] == "forbidden"
    assert status["error"] == "scope_mismatch"

    with grade_table[1]() as db:
        assert db.query(CanvasGradeRun).filter(
            CanvasGradeRun.app_id == app_id).count() == 0
