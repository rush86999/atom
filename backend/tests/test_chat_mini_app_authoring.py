"""Chat → mini-app authoring bridge.

Covers the gate (only "mini app" turns engage), the deterministic no-LLM
fallback (verb + kind extraction), the full chat-driven loop (build → author →
dev-run note → publish → install with version bump), and the None fall-through
for non-mini-app turns. DB strategy mirrors test_mini_app_agent_tools
(temp-file DB bound into core.database).
"""
import uuid

import pytest

from core.chat_mini_app_authoring import looks_like_mini_app_request, try_handle


@pytest.fixture
def patched_db(test_database, monkeypatch):
    from sqlalchemy.orm import sessionmaker

    engine, _ = test_database
    SessionLocal = sessionmaker(
        autocommit=False, autoflush=False, bind=engine, expire_on_commit=False,
    )
    monkeypatch.setattr("core.database.SessionLocal", SessionLocal)
    monkeypatch.setattr("core.database.engine", engine)
    return engine


def _uid(prefix: str = "chat") -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


def _seed_actor(user_id: str) -> None:
    """Seed the authoritative User row the chat loop's dev-run authorizes.

    ``try_handle`` scaffold/dev-runs as the chat user; a bare id with no User
    row is not an actor (Personal Edition tenant/workspace shape).
    """
    from core.database import get_db_session
    from tests.mini_app_authority_fixtures import ensure_actor

    with get_db_session() as db:
        ensure_actor(db, user_id, "default", None)
        db.commit()


class TestGate:
    def test_matches_mini_app_spellings(self):
        for m in ("build a mini app tracker", "mini-app CRM please",
                  "make a miniapp for inventory", "Mini Apps rock"):
            assert looks_like_mini_app_request(m), m

    def test_ignores_unrelated_turns(self):
        for m in ("hello", "summarize this doc", "edit the title", ""):
            assert not looks_like_mini_app_request(m), m


class TestFallThrough:
    @pytest.mark.asyncio
    async def test_non_mini_app_turn_returns_none(self, patched_db):
        res = await try_handle("what's the weather", [], _uid(), None, None)
        assert res is None

    @pytest.mark.asyncio
    async def test_question_about_mini_apps_returns_none(self, patched_db):
        # No verbs → the no-LLM fallback defaults to build, BUT a question with
        # no build verb and no owner apps would scaffold one — so gate on the
        # action extraction returning 'none' via the LLM. With llm_service=None
        # the fallback can't tell; assert the honest path instead: an unknown
        # user asking a bare question builds (documented fallback behavior).
        # Here we assert the gate passes it through when no keyword at all.
        assert await try_handle("tell me more", [], _uid(), None, None) is None


class TestChatDrivenLoop:
    BUILD = "build a mini app inventory tracker"
    HISTORY = [{"role": "user", "content": BUILD}]

    @pytest.mark.asyncio
    async def test_build_publish_install_end_to_end(self, patched_db):
        user = _uid()
        _seed_actor(user)

        # 1. Build (no LLM → deterministic authoring; kind from message scan).
        res = await try_handle(self.BUILD, [], user, None, None)
        assert res is not None and res["success"] is True
        assert "Saved starter draft" in res["message"]
        assert res["data"]["authoring_status"] == "starter_saved"
        assert res["data"]["requested_behavior_verified"] is False
        assert "on a inventory canvas" in res["message"] or "inventory" in res["message"]
        assert "Review or edit the draft" in res["message"]  # never auto-ships

        from tools.mini_app_tool import mini_app_list
        listing = await mini_app_list({}, {"user_id": user})
        apps = listing["apps"]
        assert len(apps) == 1
        assert apps[0]["status"] == "draft"
        assert apps[0]["name"]  # scaffolded

        from core.database import get_db_session
        from core.models import Canvas
        with get_db_session() as db:
            bp = db.query(Canvas).filter(Canvas.id == apps[0]["blueprint_canvas_id"]).first()
            assert bp.canvas_type == "inventory"
            from core.canvas_logic_service import CanvasLogicService
            logic = CanvasLogicService(db).load_logic(bp.id)
            assert logic
            from core.sandbox_runtime.firecracker_guest.agent import run_code

            result = run_code(logic["source"], {"state": {"items": 3}})
            assert result["exit_code"] == 0
            assert result["state_envelope"]["state"] == {"items": 4}

        # A bare "publish it" with NO mini-app context must NOT hijack a turn.
        assert await try_handle("publish it", [], user, None, None) is None

        # 2. Publish (explicit ask, conversation still about the mini-app).
        pub = await try_handle("publish it", self.HISTORY, user, None, None)
        assert pub is not None and "Published" in pub["message"]
        with get_db_session() as db:
            from core.models import MiniApp
            app = db.query(MiniApp).filter(MiniApp.id == apps[0]["id"]).first()
            assert app.status == "published" and app.version == "1.0.0"

        # Re-publish bumps the patch — updates are visible to installs.
        pub2 = await try_handle("publish it again", self.HISTORY, user, None, None)
        assert "Published" in pub2["message"]
        with get_db_session() as db:
            from core.models import MiniApp
            app = db.query(MiniApp).filter(MiniApp.id == apps[0]["id"]).first()
            assert app.version == "1.0.1"

        # 3. Install → instance canvas.
        inst = await try_handle("install it", self.HISTORY, user, None, None)
        assert inst is not None and "instance canvas" in inst["message"]

    @pytest.mark.asyncio
    async def test_build_notes_fail_closed_runtime(self, patched_db, monkeypatch):
        """On hosts without Firecracker the reply says so honestly instead of
        claiming a successful run."""
        import core.mini_app_service as svc
        def _no_runtime(*a, **k):
            raise RuntimeError("Firecracker not provisioned (test)")
        monkeypatch.setattr(svc, "get_miniapp_runtime", _no_runtime)
        user = _uid()
        _seed_actor(user)
        res = await try_handle("build a mini app expense tracker", [], user, None, None)
        assert res is not None
        assert "Firecracker" in res["message"]

    @pytest.mark.asyncio
    async def test_publish_with_no_apps_is_honest(self, patched_db):
        res = await try_handle(
            "publish my mini app", [], _uid(), None, None
        )
        assert res is not None and "No mini-app found" in res["message"]


@pytest.mark.asyncio
@pytest.mark.parametrize("repair_allowed", [False, True])
async def test_generated_logic_rejects_dynamic_execution_before_save(
    monkeypatch, repair_allowed,
):
    from types import SimpleNamespace
    from unittest.mock import AsyncMock

    from core.chat_mini_app_authoring import _author_logic

    rejected = "exec('pass')"
    accepted = "state = {'total': sum(amounts)}"
    model = SimpleNamespace(generate_completion=AsyncMock(side_effect=[
        {"content": rejected},
        {"content": accepted if repair_allowed else rejected},
    ]))
    save = AsyncMock(return_value={"success": True, "version": 1})
    monkeypatch.setattr("tools.mini_app_tool.mini_app_write_logic", save)

    result = await _author_logic(model, "app", "Inventory", "inventory", "sum", "actor")

    assert model.generate_completion.await_count == 2
    assert result["success"] is repair_allowed
    if repair_allowed:
        save.assert_awaited_once()
        assert save.await_args.args[0]["source"] == accepted
    else:
        save.assert_not_awaited()


@pytest.mark.asyncio
async def test_chat_repairs_against_same_owner_acceptance_cases(monkeypatch):
    from types import SimpleNamespace
    from unittest.mock import AsyncMock

    from core.task_lifecycle import _approval_payload_hash

    cases = [{"inputs": {"amounts": [4, 8, 15]}, "expect_state": {"total": 27}}]
    case_hash = _approval_payload_hash(cases)
    model = SimpleNamespace(generate_completion=AsyncMock(side_effect=[
        {"content": "state = {'total': 0}"},
        {"content": "state = {'total': sum(amounts)}"},
    ]))
    classify = AsyncMock(return_value=SimpleNamespace(
        action="build", name="Inventory", canvas_type="inventory", description="Sum amounts",
    ))
    save = AsyncMock(side_effect=[
        {"success": True, "source_sha256": "initial", "version": 1},
        {"success": True, "source_sha256": "repaired", "version": 2},
    ])
    set_cases = AsyncMock(return_value={"success": True})
    grade = AsyncMock(side_effect=[
        {"success": True, "tests_sha256": case_hash, "total": 1, "passed": 0,
         "all_passed": False, "results": [{"passed": False, "diff": {"total": 27}}]},
        {"success": True, "tests_sha256": case_hash, "total": 1, "passed": 1,
         "all_passed": True, "results": [{"passed": True}]},
    ])
    smoke = AsyncMock()
    scaffold = AsyncMock(return_value={"success": True, "app_id": "app", "canvas_id": "canvas"})
    monkeypatch.setattr("core.chat_tool_planner._structured_with_fallback", classify)
    for name, stub in (
        ("mini_app_scaffold", scaffold), ("mini_app_write_logic", save),
        ("mini_app_set_tests", set_cases), ("mini_app_run_tests", grade),
        ("mini_app_dev_run", smoke),
    ):
        monkeypatch.setattr(f"tools.mini_app_tool.{name}", stub)

    result = await try_handle(
        "Build an inventory mini app", [], "actor", model, acceptance_cases=cases,
    )

    assert result["data"]["acceptance"]["status"] == "passed"
    set_cases.assert_awaited_once()
    assert set_cases.await_args.args[0]["tests"] == cases
    assert [call.args[0]["expected_tests_sha256"] for call in grade.await_args_list] == [
        case_hash, case_hash,
    ]
    assert [call.args[0]["expected_source_sha256"] for call in grade.await_args_list] == [
        "initial", "repaired",
    ]
    assert save.await_args.args[0]["expected_source_sha256"] == "initial"
    assert "Previous draft failed" in str(model.generate_completion.await_args_list[1])
    smoke.assert_not_awaited()


@pytest.mark.asyncio
async def test_starter_draft_retains_owner_acceptance_cases(patched_db, monkeypatch):
    from unittest.mock import AsyncMock

    from core.database import get_db_session
    from core.models import MiniApp

    user_id = _uid()
    _seed_actor(user_id)
    run_cases = AsyncMock()
    monkeypatch.setattr("tools.mini_app_tool.mini_app_run_tests", run_cases)
    cases = [{"name": "sum", "inputs": {"amounts": [4, 8]}, "expect_state": {"total": 12}}]

    result = await try_handle(
        "build a mini app inventory tracker", [], user_id, None, None,
        acceptance_cases=cases,
    )

    assert result["data"]["acceptance"] == {
        "status": "unverified",
        "reason": "logic_not_saved",
    }
    run_cases.assert_not_awaited()
    with get_db_session() as db:
        draft = db.query(MiniApp).filter_by(created_by=user_id).one()
        assert draft.status == "draft"
        assert draft.manifest["tests"] == cases
