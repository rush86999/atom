"""Canvas co-editor chat path: core.chat_canvas_editor + orchestrator wiring.

Regression context (Aug 30, 2026): messages sent from the /canvas/{id} "Agent
Co-Editor" panel were canvas-blind — the LLM never saw the canvas, the
read-only tool planner can't write, and edit requests were misfiled by the
intent router into TASKS (creating junk local tasks). These tests pin the
new behavior: canvas-context turns either edit the canvas through
canvas_crud_tool (durable + broadcast) or fall through to the normal path.
"""
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.chat_canvas_editor import (
    CanvasEditPlan,
    apply_canvas_edit,
    plan_canvas_edit,
)


def _canvas(content=None):
    return {
        "canvas_id": "c-123",
        "canvas_type": "document",
        "title": "Draft",
        "content": content if content is not None else {"type": "doc", "content": "Hello"},
    }


# ───────────────────────── plan_canvas_edit ─────────────────────────

@pytest.mark.asyncio
async def test_plan_returns_none_without_llm_service():
    assert await plan_canvas_edit("edit this", [], _canvas(), None) is None


@pytest.mark.asyncio
async def test_plan_returns_none_without_canvas_id():
    llm = MagicMock()
    assert await plan_canvas_edit("edit this", [], {"canvas_id": None}, llm) is None


@pytest.mark.asyncio
async def test_plan_builds_prompt_with_canvas_content_and_pins_model():
    llm = MagicMock()
    llm._get_handler.return_value.clients = {"openrouter": object()}
    llm.generate_structured_response = AsyncMock(return_value=CanvasEditPlan(wants_edit=True))
    plan = await plan_canvas_edit(
        "remove the sign-off from the draft",
        [{"message": "draft an email to Mark"}],
        _canvas(),
        llm,
    )
    assert plan is not None and plan.wants_edit
    kwargs = llm.generate_structured_response.call_args.kwargs
    assert "remove the sign-off" in kwargs["prompt"]
    assert "Hello" in kwargs["prompt"]          # current content rides along
    assert "draft an email to Mark" in kwargs["prompt"]  # history for follow-ups
    assert kwargs["provider_model"][0] == "openrouter"   # pinned, planner-style


@pytest.mark.asyncio
async def test_plan_survives_history_with_no_user_turns():
    llm = MagicMock()
    llm._get_handler.return_value.clients = {}
    llm.generate_structured_response = AsyncMock(return_value=None)
    assert await plan_canvas_edit("hi", [{}], _canvas(), llm) is None


# ───────────────────────── apply_canvas_edit ─────────────────────────

@pytest.mark.asyncio
async def test_apply_persists_full_content_through_crud_tool():
    plan = CanvasEditPlan(
        wants_edit=True,
        updated_content_json=json.dumps({"type": "doc", "content": "New body"}),
        title="Draft v2",
        reply="Removed the sign-off.",
    )
    with patch("tools.canvas_crud_tool.update_canvas_content", new=AsyncMock(
        return_value={"success": True, "canvas_id": "c-123"}
    )) as upd:
        result = await apply_canvas_edit(plan, "user-1", _canvas())
    assert result and result["success"]
    upd.assert_awaited_once()
    args = upd.await_args.args
    assert args[0] == "user-1" and args[1] == "c-123"
    assert args[2] == {"type": "doc", "content": "New body"}  # decoded, full
    assert args[3] == "document"
    assert args[4] == "Draft v2"


@pytest.mark.asyncio
async def test_apply_discards_malformed_json_for_object_content():
    plan = CanvasEditPlan(wants_edit=True, updated_content_json="not json {")
    assert await apply_canvas_edit(plan, "user-1", _canvas()) is None


@pytest.mark.asyncio
async def test_apply_accepts_bare_string_for_string_content():
    plan = CanvasEditPlan(wants_edit=True, updated_content_json="plain new body")
    canvas = _canvas(content="plain old body")
    with patch("tools.canvas_crud_tool.update_canvas_content", new=AsyncMock(
        return_value={"success": True}
    )) as upd:
        result = await apply_canvas_edit(plan, "user-1", canvas)
    assert result and upd.await_args.args[2] == "plain new body"


@pytest.mark.asyncio
async def test_apply_returns_none_when_no_edit_requested():
    plan = CanvasEditPlan(wants_edit=False, reply="just talking")
    with patch("tools.canvas_crud_tool.update_canvas_content", new=AsyncMock()) as upd:
        assert await apply_canvas_edit(plan, "user-1", _canvas()) is None
    upd.assert_not_awaited()


@pytest.mark.asyncio
async def test_apply_returns_none_when_crud_fails():
    plan = CanvasEditPlan(
        wants_edit=True,
        updated_content_json=json.dumps({"type": "doc", "content": "x"}),
    )
    with patch("tools.canvas_crud_tool.update_canvas_content", new=AsyncMock(
        return_value={"success": False, "error": "Canvas c-123 not found"}
    )):
        assert await apply_canvas_edit(plan, "user-1", _canvas()) is None


@pytest.mark.asyncio
async def test_apply_returns_none_on_crud_exception():
    plan = CanvasEditPlan(
        wants_edit=True,
        updated_content_json=json.dumps({"type": "doc", "content": "x"}),
    )
    with patch("tools.canvas_crud_tool.update_canvas_content", new=AsyncMock(
        side_effect=RuntimeError("db down")
    )):
        assert await apply_canvas_edit(plan, "user-1", _canvas()) is None


# ─────────────────── orchestrator wiring (routing) ───────────────────

def _orch():
    from integrations.chat_orchestrator import ChatOrchestrator
    orch = ChatOrchestrator()
    orch.ai_engines = {}
    orch.llm_service = MagicMock()
    return orch


@pytest.mark.asyncio
async def test_canvas_edit_turn_returns_early_without_feature_routing():
    orch = _orch()
    canvas = _canvas()
    plan = CanvasEditPlan(
        wants_edit=True,
        updated_content_json=json.dumps({"type": "doc", "content": "New"}),
        reply="Trimmed the draft.",
    )
    session = {"id": "s1", "history": []}

    with patch.object(orch, "_record_chat_step", new=AsyncMock()), \
         patch("core.chat_canvas_editor.plan_canvas_edit", new=AsyncMock(return_value=plan)), \
         patch("core.chat_canvas_editor.apply_canvas_edit", new=AsyncMock(
             return_value={"success": True, "canvas_id": "c-123"})), \
         patch.object(orch, "_update_session") as upd, \
         patch.object(orch, "_emit_agent_status", new=AsyncMock()), \
         patch.object(orch, "_finish_chat_execution") as finish:
        resp = await orch._try_canvas_edit(
            "trim the draft", [], canvas, "user-1", "s1", "exec-1", None
        )

    assert resp and resp["success"] and resp["message"] == "Trimmed the draft."
    assert resp["intent"] == "canvas_edit"

    # Full-turn wiring: process_chat_message persists the turn and skips the
    # intent router / feature handlers entirely for handled edits.
    with patch.object(orch, "_get_or_create_session", return_value=session), \
         patch.object(orch, "_start_chat_execution", return_value="exec-1"), \
         patch.object(orch, "_emit_agent_status", new=AsyncMock()), \
         patch.object(orch, "_try_canvas_edit", new=AsyncMock(return_value=resp)), \
         patch.object(orch, "_get_qwen_response", new=AsyncMock()) as qwen, \
         patch.object(orch, "_analyze_intent", new=AsyncMock()) as analyze, \
         patch.object(orch, "_route_to_features", new=AsyncMock()) as route, \
         patch.object(orch, "_update_session") as upd, \
         patch.object(orch, "_finish_chat_execution") as finish:
        out = await orch.process_chat_message(
            user_id="user-1",
            message="trim the draft",
            session_id="s1",
            context={"canvas_id": "c-123", "canvas_type": "document",
                     "canvas_content": {"type": "doc", "content": "Old"}},
        )

    assert out["success"] and out["intent"] == "canvas_edit"
    qwen.assert_not_awaited()      # no double LLM call for an edit turn
    analyze.assert_not_awaited()   # no intent misclassification…
    route.assert_not_called()      # …and no TASKS/AUTOMATION side effects
    upd.assert_called()
    finish.assert_called()


@pytest.mark.asyncio
async def test_non_edit_canvas_turn_falls_through_to_normal_path():
    orch = _orch()
    session = {"id": "s2", "history": []}
    canvas_noop = None  # _try_canvas_edit returns None → normal path

    with patch.object(orch, "_get_or_create_session", return_value=session), \
         patch.object(orch, "_start_chat_execution", return_value="exec-2"), \
         patch.object(orch, "_emit_agent_status", new=AsyncMock()), \
         patch.object(orch, "_try_canvas_edit", new=AsyncMock(return_value=canvas_noop)), \
         patch.object(orch, "_get_qwen_response", new=AsyncMock(return_value={
             "content": "Here's what the draft says…", "model": "m", "provider": "p",
         })) as qwen, \
         patch.object(orch, "_analyze_intent", new=AsyncMock(return_value={
             "primary_intent": MagicMock(value="search"), "confidence": 0.9,
         })), \
         patch.object(orch, "_route_to_features", new=AsyncMock(return_value={})), \
         patch.object(orch, "_dispatch_turn_fact_extraction"), \
         patch.object(orch, "_update_session"), \
         patch.object(orch, "_finish_chat_execution"), \
         patch.object(orch, "_emit_agent_status", new=AsyncMock()):
        out = await orch.process_chat_message(
            user_id="user-1",
            message="what does the draft currently say?",
            session_id="s2",
            context={"canvas_id": "c-123", "canvas_type": "document",
                     "canvas_content": {"type": "doc", "content": "Old"}},
        )

    # Normal path ran, and the canvas context was threaded into the LLM call.
    qwen.assert_awaited_once()
    assert qwen.await_args.kwargs["canvas_context"]["canvas_id"] == "c-123"
    assert "draft" in out["message"].lower()


@pytest.mark.asyncio
async def test_turn_without_canvas_context_skips_edit_step_entirely():
    orch = _orch()
    session = {"id": "s3", "history": []}
    with patch.object(orch, "_get_or_create_session", return_value=session), \
         patch.object(orch, "_start_chat_execution", return_value="exec-3"), \
         patch.object(orch, "_emit_agent_status", new=AsyncMock()), \
         patch.object(orch, "_try_canvas_edit", new=AsyncMock()) as try_edit, \
         patch.object(orch, "_get_qwen_response", new=AsyncMock(return_value={
             "content": "ok", "model": "m", "provider": "p",
         })), \
         patch.object(orch, "_analyze_intent", new=AsyncMock(return_value={
             "primary_intent": MagicMock(value="search"), "confidence": 0.9,
         })), \
         patch.object(orch, "_route_to_features", new=AsyncMock(return_value={})), \
         patch.object(orch, "_dispatch_turn_fact_extraction"), \
         patch.object(orch, "_update_session"), \
         patch.object(orch, "_finish_chat_execution"), \
         patch.object(orch, "_emit_agent_status", new=AsyncMock()):
        await orch.process_chat_message(
            user_id="user-1", message="hello", session_id="s3",
            context={"current_page": "/chat"},
        )
    try_edit.assert_not_awaited()  # plain /chat turns must not pay the cost


# ─────────────────── canvas↔session binding (DB-backed) ───────────────────

def test_bind_canvas_chat_session_persists_binding():
    from unittest.mock import patch, MagicMock
    from integrations.chat_routes import _bind_canvas_chat_session

    svc = MagicMock()
    svc.update_state.return_value = True
    with patch("core.service_factory.ServiceFactory.get_canvas_context_service", return_value=svc), \
         patch("core.database.get_db_session") as dbs:
        dbs.return_value.__enter__ = MagicMock(return_value=MagicMock())
        dbs.return_value.__exit__ = MagicMock(return_value=False)
        ok = _bind_canvas_chat_session(
            canvas_id="c-1", canvas_type="document", user_id="u-1",
            tenant_id="default", agent_id=None, session_id="s-1",
        )

    assert ok is True
    svc.get_or_create_context.assert_called_once_with(
        canvas_id="c-1", canvas_type="document", user_id="u-1", agent_id=None)
    svc.update_state.assert_called_once_with(
        canvas_id="c-1", user_id="u-1",
        state_update={"chat_session_id": "s-1"})


def test_bind_canvas_chat_session_skips_placeholder_ids():
    from integrations.chat_routes import _bind_canvas_chat_session
    with patch("integrations.chat_routes.logger") as log:
        assert _bind_canvas_chat_session(None, "document", "u-1", "default", None, "s-1") is False
        assert _bind_canvas_chat_session("c-1", "document", "u-1", "default", None, "new") is False
        assert _bind_canvas_chat_session("c-1", "document", "u-1", "default", None, None) is False


def test_bind_canvas_chat_session_never_raises():
    from integrations.chat_routes import _bind_canvas_chat_session
    with patch("core.service_factory.ServiceFactory.get_canvas_context_service",
               side_effect=RuntimeError("db down")):
        ok = _bind_canvas_chat_session(
            canvas_id="c-1", canvas_type="document", user_id="u-1",
            tenant_id="default", agent_id=None, session_id="s-1")
    assert ok is False


# ───────────── durability: fresh installs + restart survival ─────────────

def _fresh_engine(tmp_path, name):
    """New-install simulation: brand-new sqlite file, schema created the way
    app startup does it (Base.metadata.create_all)."""
    from core.models import Base
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    eng = create_engine(f"sqlite:///{tmp_path}/{name}.db")
    Base.metadata.create_all(bind=eng)
    return eng, sessionmaker(bind=eng, expire_on_commit=False)


def _hermetic_factory_patch():
    """Bypass ServiceFactory's thread-local service cache. The cache pins the
    FIRST db session a thread ever handed it — across tests (and plausibly
    across requests in the API server, holding long read transactions open).
    Each call gets a fresh service bound to the CURRENT session."""
    from unittest.mock import patch
    from services.canvas_context_service import CanvasContextService

    return patch(
        "core.service_factory.ServiceFactory.get_canvas_context_service",
        classmethod(lambda cls, db, tenant_id: CanvasContextService(db, tenant_id=tenant_id)),
    )


def test_binding_works_on_fresh_install_and_survives_restart(tmp_path):
    """New installation → first canvas turn binds → backend restart → the
    panel's read path still resolves the binding and the transcript."""
    import contextlib
    from unittest.mock import patch

    from core.models import CanvasContext, ChatMessage
    from integrations.chat_routes import _bind_canvas_chat_session
    from services.canvas_context_service import CanvasContextService

    # ── "new install": empty DB, tables created at startup ──
    eng1, Session1 = _fresh_engine(tmp_path, "install1")

    @contextlib.contextmanager
    def db_session_1():
        s = Session1()
        try:
            yield s
        finally:
            s.close()

    with _hermetic_factory_patch(), \
         patch("core.database.get_db_session", side_effect=lambda: db_session_1()):
        ok = _bind_canvas_chat_session(
            canvas_id="c-new", canvas_type="document", user_id="u-new",
            tenant_id="default", agent_id=None, session_id="s-new",
        )
    assert ok is True

    # transcript rows as _update_session writes them (DB-only session)
    with db_session_1() as s:
        s.add(ChatMessage(conversation_id="s-new", tenant_id="default",
                          role="user", content="tighten the draft"))
        s.add(ChatMessage(conversation_id="s-new", tenant_id="default",
                          role="assistant", content="Tightened."))
        s.commit()
    eng1.dispose()  # process exits

    # ── "restart": brand-new engine/process on the same DB file ──
    eng2, Session2 = _fresh_engine(tmp_path, "install1")  # create_all is a no-op now
    with Session2() as s:
        svc = CanvasContextService(s, tenant_id="default")
        snap = svc.get_context_snapshot(canvas_id="c-new", user_id="u-new")
        assert snap.get("current_state", {}).get("chat_session_id") == "s-new"

        rows = (s.query(ChatMessage)
                 .filter(ChatMessage.conversation_id == "s-new")
                 .order_by(ChatMessage.created_at).all())
        assert [r.role for r in rows] == ["user", "assistant"]
        assert [r.content for r in rows] == ["tighten the draft", "Tightened."]
    eng2.dispose()


def test_binding_is_idempotent_and_latest_session_wins(tmp_path):
    import contextlib
    from unittest.mock import patch

    from core.models import CanvasContext
    from integrations.chat_routes import _bind_canvas_chat_session
    from services.canvas_context_service import CanvasContextService

    eng, Sess = _fresh_engine(tmp_path, "install2")

    @contextlib.contextmanager
    def db_session():
        s = Sess()
        try:
            yield s
        finally:
            s.close()

    with _hermetic_factory_patch(), \
         patch("core.database.get_db_session", side_effect=lambda: db_session()):
        assert _bind_canvas_chat_session("c-x", "document", "u-x", "default", None, "s-1") is True
        assert _bind_canvas_chat_session("c-x", "document", "u-x", "default", None, "s-2") is True

    with Sess() as s:
        assert s.query(CanvasContext).filter(CanvasContext.canvas_id == "c-x").count() == 1
        assert CanvasContextService(s, tenant_id="default").get_context_snapshot(
            "c-x", "u-x")["current_state"]["chat_session_id"] == "s-2"
    eng.dispose()


# ───────────── canvas has an agent; immature hires learn ─────────────

def _seed_agent(eng_session, agent_id, status="student"):
    from core.models import AgentRegistry
    agent = AgentRegistry(id=agent_id, name="Hire", category="business",
                          module_path="core.test", class_name="T",
                          status=status, tenant_id="default")
    eng_session.add(agent)
    eng_session.commit()
    return agent


def test_resolve_canvas_agent_prefers_context_binding(tmp_path):
    import contextlib
    from unittest.mock import patch
    from integrations.chat_routes import _resolve_canvas_agent_id
    from core.models import CanvasContext

    eng, Sess = _fresh_engine(tmp_path, "resolve1")

    @contextlib.contextmanager
    def db_session():
        s = Sess()
        try:
            yield s
        finally:
            s.close()

    with Sess() as s:
        _seed_agent(s, "agent-bound")
        _seed_agent(s, "agent-audit")
        s.add(CanvasContext(canvas_id="c-r", tenant_id="default",
                            canvas_type="document", user_id="u-r",
                            agent_id="agent-bound",
                            current_state={}))
        s.commit()

    with patch("core.database.get_db_session", side_effect=lambda: db_session()):
        assert _resolve_canvas_agent_id("c-r", "default") == "agent-bound"
    eng.dispose()


def test_resolve_canvas_agent_falls_back_to_audit_and_skips_dead_agents(tmp_path):
    import contextlib
    from unittest.mock import patch
    from integrations.chat_routes import _resolve_canvas_agent_id
    from core.models import CanvasAudit

    eng, Sess = _fresh_engine(tmp_path, "resolve2")

    @contextlib.contextmanager
    def db_session():
        s = Sess()
        try:
            yield s
        finally:
            s.close()

    with Sess() as s:
        # Audit names a DELETED agent first, then a live one.
        s.add(CanvasAudit(canvas_id="c-a2", tenant_id="default",
                          canvas_type="document", action_type="present",
                          user_id="u-r", agent_id="agent-gone",
                          details_json={"content": "x"}))
        s.add(CanvasAudit(canvas_id="c-a2", tenant_id="default",
                          canvas_type="document", action_type="update",
                          user_id="u-r", agent_id="agent-live",
                          details_json={"content": "y"}))
        _seed_agent(s, "agent-live")
        s.commit()

    with patch("core.database.get_db_session", side_effect=lambda: db_session()):
        assert _resolve_canvas_agent_id("c-a2", "default") == "agent-live"
        assert _resolve_canvas_agent_id("c-unknown", "default") is None
    eng.dispose()


@pytest.mark.asyncio
async def test_immature_hire_edits_in_learning_mode():
    """Not mature enough (update_canvas is INTERN+) is NOT a refusal: the
    hire proposes the edit as a draft, the reply invites correction, and the
    proposal lands in the canvas's training context."""
    orch = _orch()
    canvas = _canvas()
    plan = CanvasEditPlan(
        wants_edit=True,
        updated_content_json=json.dumps({"type": "doc", "content": "Draft"}),
        reply="Trimmed it.",
    )
    gov = MagicMock()
    gov.can_perform_action.return_value = {"allowed": False, "reason": "maturity: student < intern"}
    ctx_svc = MagicMock()
    with patch.object(orch, "_record_chat_step", new=AsyncMock()), \
         patch("core.chat_canvas_editor.plan_canvas_edit", new=AsyncMock(return_value=plan)), \
         patch("core.chat_canvas_editor.apply_canvas_edit", new=AsyncMock(
             return_value={"success": True})) as apply_mock, \
         patch("core.service_factory.ServiceFactory.get_governance_service", return_value=gov), \
         patch("core.service_factory.ServiceFactory.get_canvas_context_service", return_value=ctx_svc):
        resp = await orch._try_canvas_edit(
            "tighten the draft", [], canvas, "user-1", "s-learn", "exec-1", "hire-1",
        )

    assert resp and resp["success"]
    assert resp["data"]["canvas_edit"]["learning_mode"] is True
    assert "still learning" in resp["message"]
    apply_mock.assert_awaited_once()          # the edit still happens (draft)
    assert ctx_svc.add_action_to_history.call_count == 1
    recorded = ctx_svc.add_action_to_history.call_args.kwargs["action"]
    assert recorded["type"] == "canvas_edit_proposal" and recorded["learning_mode"]


@pytest.mark.asyncio
async def test_mature_hire_edits_normally():
    orch = _orch()
    plan = CanvasEditPlan(
        wants_edit=True,
        updated_content_json=json.dumps({"type": "doc", "content": "Final"}),
        reply="Done.",
    )
    gov = MagicMock()
    gov.can_perform_action.return_value = {"allowed": True}
    ctx_svc = MagicMock()
    with patch.object(orch, "_record_chat_step", new=AsyncMock()), \
         patch("core.chat_canvas_editor.plan_canvas_edit", new=AsyncMock(return_value=plan)), \
         patch("core.chat_canvas_editor.apply_canvas_edit", new=AsyncMock(
             return_value={"success": True})), \
         patch("core.service_factory.ServiceFactory.get_governance_service", return_value=gov), \
         patch("core.service_factory.ServiceFactory.get_canvas_context_service", return_value=ctx_svc):
        resp = await orch._try_canvas_edit(
            "tighten the draft", [], _canvas(), "user-1", "s-1", "exec-1", "hire-1",
        )

    assert resp and resp["success"]
    assert "learning_mode" not in resp["data"]["canvas_edit"]
    assert "still learning" not in resp["message"]
    ctx_svc.add_action_to_history.assert_not_called()


@pytest.mark.asyncio
async def test_no_agent_means_no_governance_gate():
    """Platform-assistant turns (no resolved hire) keep today's behavior."""
    orch = _orch()
    plan = CanvasEditPlan(wants_edit=True, updated_content_json='{"a": 1}', reply="ok")
    with patch.object(orch, "_record_chat_step", new=AsyncMock()), \
         patch("core.chat_canvas_editor.plan_canvas_edit", new=AsyncMock(return_value=plan)), \
         patch("core.chat_canvas_editor.apply_canvas_edit", new=AsyncMock(
             return_value={"success": True})), \
         patch("core.service_factory.ServiceFactory.get_governance_service") as gov:
        resp = await orch._try_canvas_edit(
            "edit it", [], _canvas(), "user-1", "s-1", "exec-1", None,
        )
    assert resp and resp["success"]
    gov.assert_not_called()


def test_supervisor_correction_feeds_learning_loop(tmp_path):
    """PUT after an agent draft = the correction signal (RLHF)."""
    import contextlib
    from unittest.mock import patch
    from api.canvas_routes import _maybe_record_canvas_correction
    from core.models import CanvasContext, CanvasAudit
    from services.canvas_context_service import CanvasContextService

    eng, Sess = _fresh_engine(tmp_path, "correct1")

    @contextlib.contextmanager
    def db_session():
        s = Sess()
        try:
            yield s
        finally:
            s.close()

    with patch("core.database.get_db_session", side_effect=lambda: db_session()):
        with Sess() as s:
            _seed_agent(s, "hire-9")
            s.add(CanvasContext(canvas_id="c-corr", tenant_id="default",
                                canvas_type="document", user_id="u-9",
                                agent_id="hire-9", current_state={}))
            # older: agent's draft; newer: the supervisor's save (appended by
            # the route before the capture runs)
            from datetime import datetime, timedelta
            _t0 = datetime(2026, 8, 30, 12, 0, 0)
            s.add(CanvasAudit(canvas_id="c-corr", tenant_id="default",
                              canvas_type="document", action_type="update",
                              user_id="u-9", agent_id="hire-9",
                              created_at=_t0,
                              details_json={"content": {"draft": True}}))
            s.commit()
        with Sess() as s:
            from datetime import datetime, timedelta
            _t1 = datetime(2026, 8, 30, 12, 1, 0)
            s.add(CanvasAudit(canvas_id="c-corr", tenant_id="default",
                              canvas_type="document", action_type="update",
                              user_id="u-9", agent_id=None,
                              created_at=_t1,
                              details_json={"content": {"fixed": True}}))
            s.commit()

        _maybe_record_canvas_correction("u-9", "default", "c-corr", {"fixed": True})

        with Sess() as s:
            ctx = s.query(CanvasContext).filter(CanvasContext.canvas_id == "c-corr").first()
            corrections = ctx.user_corrections or []
            assert len(corrections) == 1
            assert corrections[0]["original"]["content"] == {"draft": True}
            assert corrections[0]["corrected"]["content"] == {"fixed": True}
    eng.dispose()


def test_correction_capture_noops_without_agent_draft(tmp_path):
    import contextlib
    from unittest.mock import patch
    from api.canvas_routes import _maybe_record_canvas_correction
    from core.models import CanvasContext, CanvasAudit

    eng, Sess = _fresh_engine(tmp_path, "correct2")

    @contextlib.contextmanager
    def db_session():
        s = Sess()
        try:
            yield s
        finally:
            s.close()

    with patch("core.database.get_db_session", side_effect=lambda: db_session()):
        # Human-edited prior version: nothing to learn.
        with Sess() as s:
            s.add(CanvasAudit(canvas_id="c-x", tenant_id="default",
                              canvas_type="document", action_type="update",
                              user_id="u-9", agent_id=None,
                              details_json={"content": "old"}))
            s.add(CanvasAudit(canvas_id="c-x", tenant_id="default",
                              canvas_type="document", action_type="update",
                              user_id="u-9", agent_id=None,
                              details_json={"content": "new"}))
            s.commit()
        _maybe_record_canvas_correction("u-9", "default", "c-x", "new")  # must not raise

        with Sess() as s:
            ctx = s.query(CanvasContext).filter(CanvasContext.canvas_id == "c-x").first()
            assert ctx is None or not (ctx.user_corrections or [])
    eng.dispose()


# ───────────── actions, autonomy policy, and HITL proposals ─────────────

def test_autonomy_policy_defaults_and_override(tmp_path):
    import contextlib
    from unittest.mock import patch
    from core import autonomy_policy as ap

    eng, Sess = _fresh_engine(tmp_path, "autonomy1")

    @contextlib.contextmanager
    def db_session():
        s = Sess()
        try:
            yield s
        finally:
            s.close()

    with Sess() as s:
        # blast-radius defaults: external sends stay HITL
        assert ap.get_effective_mode(s, "u-1", "send_email") == ap.MODE_HUMAN_ALWAYS
        assert ap.get_effective_mode(s, "u-1", "canvas_edit") == ap.MODE_AUTO_IF_MATURE
        assert ap.get_effective_mode(s, "u-1", "crm_write") == ap.MODE_HUMAN_ALWAYS
        # owner flips send_email to autonomous
        assert ap.set_mode(s, "u-1", "send_email", ap.MODE_AUTO_IF_MATURE) is True
        assert ap.get_effective_mode(s, "u-1", "send_email") == ap.MODE_AUTO_IF_MATURE
        # other users unaffected; unknown topics default to auto
        assert ap.get_effective_mode(s, "u-2", "send_email") == ap.MODE_HUMAN_ALWAYS
        assert ap.get_effective_mode(s, "u-1", "nonexistent") == ap.MODE_AUTO_IF_MATURE
        topics = ap.list_topics("u-1", s)
        by_topic = {t["topic"]: t for t in topics}
        assert by_topic["send_email"]["mode"] == ap.MODE_AUTO_IF_MATURE  # user override
        assert by_topic["task_create"]["mode"] == ap.MODE_AUTO_IF_MATURE  # default
    eng.dispose()


@pytest.mark.asyncio
async def test_send_action_always_proposes_when_policy_demands_human():
    """human_always (the default for sends) → the agent may only PROPOSE."""
    from core.chat_canvas_editor import CanvasActionPlan

    orch = _orch()
    plan = CanvasActionPlan(
        wants_action=True, action="send_email", to="mark@example.com",
        subject="Draft", body="Body", reply="Ready to send.",
    )
    with patch.object(orch, "_record_chat_step", new=AsyncMock()), \
         patch("core.chat_canvas_editor.plan_canvas_action", new=AsyncMock(return_value=plan)), \
         patch.object(orch, "_execute_send_email", new=AsyncMock()) as exec_mock, \
         patch.object(orch, "_create_send_email_proposal", return_value="prop-1") as propose:
        resp = await orch._try_canvas_action(
            "send this to mark@example.com", [], _canvas(), "user-1", "s-1", "exec-1", "hire-1",
        )

    assert resp and resp["intent"] == "canvas_action"
    assert resp["data"]["canvas_action"]["needs_approval"] is True
    assert resp["data"]["canvas_action"]["proposal_id"] == "prop-1"
    assert "approval" in resp["message"].lower()
    exec_mock.assert_not_awaited()   # NEVER sends directly under human_always
    propose.assert_called_once()


@pytest.mark.asyncio
async def test_send_action_executes_when_autonomous_and_mature():
    import contextlib
    from core.autonomy_policy import MODE_AUTO_IF_MATURE
    from core.chat_canvas_editor import CanvasActionPlan

    orch = _orch()
    plan = CanvasActionPlan(
        wants_action=True, action="send_email", to="mark@example.com",
        subject="Draft", body="Body", reply="Sending.",
    )
    gov = MagicMock()
    gov.can_perform_action.return_value = {"allowed": True}

    @contextlib.contextmanager
    def db_session():
        yield MagicMock()

    with patch.object(orch, "_record_chat_step", new=AsyncMock()), \
         patch("core.chat_canvas_editor.plan_canvas_action", new=AsyncMock(return_value=plan)), \
         patch("core.autonomy_policy.get_effective_mode", return_value=MODE_AUTO_IF_MATURE), \
         patch("core.service_factory.ServiceFactory.get_governance_service", return_value=gov), \
         patch("core.database.get_db_session", side_effect=lambda: db_session()), \
         patch.object(orch, "_execute_send_email", new=AsyncMock(return_value={
             "action": "send_email", "status": "sent", "message": "Email sent to mark@example.com.",
         })) as exec_mock:
        resp = await orch._try_canvas_action(
            "send this to mark@example.com", [], _canvas(), "user-1", "s-1", "exec-1", "hire-1",
        )

    assert resp and resp["intent"] == "canvas_action"
    assert "sent" in resp["message"].lower()
    exec_mock.assert_awaited_once()


@pytest.mark.asyncio
async def test_send_action_proposes_when_autonomous_but_immature():
    import contextlib
    from core.autonomy_policy import MODE_AUTO_IF_MATURE
    from core.chat_canvas_editor import CanvasActionPlan

    orch = _orch()
    plan = CanvasActionPlan(
        wants_action=True, action="send_email", to="mark@example.com",
        subject="Draft", body="Body", reply="Sending.",
    )
    gov = MagicMock()
    gov.can_perform_action.return_value = {"allowed": False, "reason": "maturity"}

    @contextlib.contextmanager
    def db_session():
        yield MagicMock()

    with patch.object(orch, "_record_chat_step", new=AsyncMock()), \
         patch("core.chat_canvas_editor.plan_canvas_action", new=AsyncMock(return_value=plan)), \
         patch("core.autonomy_policy.get_effective_mode", return_value=MODE_AUTO_IF_MATURE), \
         patch("core.service_factory.ServiceFactory.get_governance_service", return_value=gov), \
         patch("core.database.get_db_session", side_effect=lambda: db_session()), \
         patch.object(orch, "_execute_send_email", new=AsyncMock()) as exec_mock, \
         patch.object(orch, "_create_send_email_proposal", return_value="prop-2"):
        resp = await orch._try_canvas_action(
            "send this to mark@example.com", [], _canvas(), "user-1", "s-1", "exec-1", "hire-1",
        )

    assert resp and resp["data"]["canvas_action"]["needs_approval"] is True
    assert "isn't mature enough" in resp["message"]
    exec_mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_non_action_messages_fall_through():
    from core.chat_canvas_editor import CanvasActionPlan
    orch = _orch()
    plan = CanvasActionPlan(wants_action=False, reply="")
    with patch("core.chat_canvas_editor.plan_canvas_action", new=AsyncMock(return_value=plan)):
        resp = await orch._try_canvas_action(
            "what do you think of the draft?", [], _canvas(), "user-1", "s-1", "exec-1", None,
        )
    assert resp is None


def test_send_email_proposal_row_created(tmp_path):
    """The HITL proposal persists as a pending AgentProposal the maturity
    endpoints can list/approve/reject."""
    import contextlib
    from unittest.mock import patch
    from core.chat_canvas_editor import CanvasActionPlan
    from core.models import AgentProposal, AgentRegistry

    eng, Sess = _fresh_engine(tmp_path, "proposal1")

    @contextlib.contextmanager
    def db_session():
        s = Sess()
        try:
            yield s
        finally:
            s.close()

    from integrations.chat_orchestrator import ChatOrchestrator
    orch = ChatOrchestrator.__new__(ChatOrchestrator)
    plan = CanvasActionPlan(wants_action=True, action="send_email",
                            to="mark@example.com", subject="S", body="B", reply="r")

    with Sess() as s:
        s.add(AgentRegistry(id="hire-p", name="SDR", category="sales", module_path="t",
                            class_name="T", status="intern", tenant_id="default"))
        s.commit()

    with patch("core.database.get_db_session", side_effect=lambda: db_session()):
        pid = orch._create_send_email_proposal(
            plan, {"canvas_id": "c-p", "title": "T", "canvas_type": "document"},
            "u-p", "s-p", "hire-p",
        )
    assert pid
    with Sess() as s:
        row = s.query(AgentProposal).filter(AgentProposal.id == pid).first()
        assert row.status == "pending_approval"
        assert row.proposal_data["action_type"] == "send_email"
        assert row.proposal_data["to"] == "mark@example.com"
        assert row.agent_name == "SDR"
    eng.dispose()


def test_journey_events_expose_actual_content(tmp_path):
    """A journey line item that hides what was actually written is an audit
    in name only — every version row must carry its content."""
    import contextlib
    from unittest.mock import patch
    from fastapi import HTTPException
    from api.canvas_routes import get_canvas_journey
    from core.models import Canvas, CanvasAudit, User
    import asyncio
    from datetime import datetime, timedelta

    eng, Sess = _fresh_engine(tmp_path, "journey1")

    @contextlib.contextmanager
    def db_session():
        s = Sess()
        try:
            yield s
        finally:
            s.close()

    class FakeUser:
        id = "u-j"
        tenant_id = "default"

    with Sess() as s:
        s.add(User(id="u-j", email="j@x", hashed_password="x",
                   first_name="J", last_name="T", role="member", status="active"))
        s.add(Canvas(id="c-j", tenant_id="default", created_by="u-j",
                     name="Draft", canvas_type="document", content={}))
        t0 = datetime(2026, 8, 30, 12, 0, 0)
        s.add(CanvasAudit(canvas_id="c-j", tenant_id="default",
                          canvas_type="document", action_type="present",
                          user_id="u-j", created_at=t0,
                          details_json={"content": {"type": "doc", "content": "Version one text"}, "title": "Draft"}))
        s.add(CanvasAudit(canvas_id="c-j", tenant_id="default",
                          canvas_type="document", action_type="update",
                          user_id="u-j", created_at=t0 + timedelta(minutes=1),
                          details_json={"content": {"type": "doc", "content": "Version two text"}, "title": "Draft"}))
        s.commit()

    async def fake_read_canvas(user_id, canvas_id):
        return {"success": True}

    with patch("tools.canvas_crud_tool.read_canvas", new=fake_read_canvas):
        with db_session() as route_db:
            result = asyncio.get_event_loop().run_until_complete(
                get_canvas_journey("c-j", current_user=FakeUser(), db=route_db)
            )

    by_action = {}
    for e in result["events"]:
        if e["kind"] == "audit":
            by_action[e["action"]] = e
    assert by_action["update"]["content"] == "Version two text"
    assert by_action["update"]["content_preview"] == "Version two text"
    assert by_action["present"]["content"] == "Version one text"


# ───────────── feedback: persists across refresh, never double-fed ─────────────

def _feedback_payload(run_id="run-1", summary="Good reply text", ftype="thumbs_up", comment=None):
    return {
        "agent_id": "hire-fb", "run_id": run_id, "step_index": -1,
        "step_content": {"input_summary": summary, "canvas_id": "c-fb", "source": "canvas_chat"},
        "feedback_type": ftype, "comment": comment,
    }


def test_identical_feedback_resubmit_creates_no_duplicate_training_rows(tmp_path):
    """Refresh clears the client thumbs state → the user re-clicks the SAME
    thumb. Each re-click used to append another AgentFeedback row and re-run
    adjudication — duplicate training data. Identical resubmits are no-ops."""
    import asyncio, contextlib, json as _json
    from unittest.mock import patch, MagicMock
    from api.reasoning_routes import submit_step_feedback
    from core.models import AgentFeedback, AgentRegistry
    from api.reasoning_routes import ReasoningStepFeedback

    eng, Sess = _fresh_engine(tmp_path, "fb1")

    @contextlib.contextmanager
    def db_session():
        s = Sess()
        try:
            yield s
        finally:
            s.close()

    # Real insert (the dedupe must FIND the first row); adjudication mocked.
    from core.models import AgentFeedback as AF
    created = {"n": 0}
    class FakeGov:
        def __init__(self, db):
            self._db = db
        async def submit_feedback(self, **kw):
            created["n"] += 1
            row = AF(agent_id=kw["agent_id"], user_id=kw["user_id"],
                     original_output=kw["original_output"],
                     user_correction=kw["user_correction"],
                     input_context=kw["input_context"])
            self._db.add(row)
            self._db.commit()
            self._db.refresh(row)
            return row

    with Sess() as s:
        s.add(AgentRegistry(id="hire-fb", name="H", category="b", module_path="t",
                            class_name="T", status="intern", tenant_id="default"))
        s.commit()
    user = MagicMock(); user.id = "u-fb"
    payload = ReasoningStepFeedback(**_feedback_payload())

    with patch("api.reasoning_routes.AgentGovernanceService", FakeGov):
        loop = asyncio.get_event_loop()
        with Sess() as db_arg:
            r1 = loop.run_until_complete(submit_step_feedback(feedback=payload, db=db_arg, current_user=user))
        with Sess() as db_arg:
            r2 = loop.run_until_complete(submit_step_feedback(feedback=payload, db=db_arg, current_user=user))

    assert created["n"] == 1, "identical resubmit must not create a second training row"
    def _dup(r):
        if isinstance(r, dict):
            return r.get("data") or {}
        d = getattr(r, "data", None)
        return d if isinstance(d, dict) else {}
    assert not _dup(r1).get("duplicate")
    assert _dup(r2).get("duplicate") is True


def test_canvas_chat_feedback_persists_and_clears(tmp_path):
    """The thumbs choice is stamped onto the canvas context (survives
    refresh) and the clear gesture nulls exactly that entry."""
    import asyncio, contextlib
    from unittest.mock import patch, MagicMock
    from api.reasoning_routes import submit_step_feedback, ReasoningStepFeedback
    from api.canvas_routes import clear_canvas_chat_feedback, ClearChatFeedbackRequest
    from core.models import CanvasContext, AgentRegistry

    eng, Sess = _fresh_engine(tmp_path, "fb2")

    @contextlib.contextmanager
    def db_session():
        s = Sess()
        try:
            yield s
        finally:
            s.close()

    class FakeRow: id = "fb-2"
    gov = MagicMock()
    gov.submit_feedback = AsyncMock(return_value=FakeRow())

    user = MagicMock(); user.id = "u-fb2"; user.tenant_id = "default"
    with Sess() as s:
        s.add(AgentRegistry(id="hire-fb", name="H", category="b", module_path="t",
                            class_name="T", status="intern", tenant_id="default"))
        s.add(CanvasContext(canvas_id="c-fb", tenant_id="default", canvas_type="document",
                            user_id="u-fb2", current_state={}))
        s.commit()

    payload = ReasoningStepFeedback(**_feedback_payload(summary="Reply A"))
    loop = asyncio.get_event_loop()
    with patch("api.reasoning_routes.AgentGovernanceService", return_value=gov), Sess() as db_arg:
        loop.run_until_complete(submit_step_feedback(feedback=payload, db=db_arg, current_user=user))

    with Sess() as s:
        ctx = s.query(CanvasContext).filter(CanvasContext.canvas_id == "c-fb").first()
        fb = (ctx.current_state or {}).get("chat_feedback") or {}
        assert fb.get("Reply A", {}).get("feedback_type") == "thumbs_up"

    # a second, DIFFERENT message keeps both entries
    payload2 = ReasoningStepFeedback(**_feedback_payload(summary="Reply B", ftype="thumbs_down"))
    with patch("api.reasoning_routes.AgentGovernanceService", return_value=gov), Sess() as db_arg:
        loop.run_until_complete(submit_step_feedback(feedback=payload2, db=db_arg, current_user=user))
    with Sess() as s:
        ctx = s.query(CanvasContext).filter(CanvasContext.canvas_id == "c-fb").first()
        fb = (ctx.current_state or {}).get("chat_feedback") or {}
        assert fb.get("Reply A", {}).get("feedback_type") == "thumbs_up"
        assert fb.get("Reply B", {}).get("feedback_type") == "thumbs_down"

    # clearing Reply A nulls only that entry
    req_obj = ClearChatFeedbackRequest(input_summary="Reply A")
    with Sess() as db_arg:
        loop.run_until_complete(clear_canvas_chat_feedback("c-fb", req_obj, current_user=user, db=db_arg))
    with Sess() as s:
        ctx = s.query(CanvasContext).filter(CanvasContext.canvas_id == "c-fb").first()
        fb = (ctx.current_state or {}).get("chat_feedback") or {}
        assert fb.get("Reply A") is None
        assert fb.get("Reply B", {}).get("feedback_type") == "thumbs_down"
    eng.dispose()
