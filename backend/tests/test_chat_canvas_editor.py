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
    CanvasPatchOp,
    _apply_patch_ops,
    apply_canvas_edit,
    plan_canvas_edit,
)


@pytest.fixture(autouse=True)
def _hermetic_canvas_store():
    """Default read_canvas to "not found" so the orchestrator's durable-store
    refresh falls back to the client context instead of touching a real DB.
    Tests that exercise the refresh patch read_canvas themselves — their mock
    applies inside this one and wins for the duration."""
    with patch(
        "tools.canvas_crud_tool.read_canvas",
        new=AsyncMock(return_value={"success": False, "error": "Canvas c-123 not found"}),
    ):
        yield


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
    llm.generate_structured_response = AsyncMock(return_value=CanvasEditPlan(
        wants_edit=True, updated_content_json='"new body"'))
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
async def test_plan_raises_when_llm_fails_entirely():
    """A dead planning LLM must be distinguishable from "not an edit": the
    orchestrator answers honestly instead of misrouting an edit request into
    TASK_MANAGEMENT, which answered with a false success claim while the
    canvas never changed (observed live Aug 31, 2026)."""
    from core.chat_canvas_editor import CanvasPlanUnavailable

    llm = MagicMock()
    llm._get_handler.return_value.clients = {}
    llm.generate_structured_response = AsyncMock(return_value=None)
    with pytest.raises(CanvasPlanUnavailable):
        await plan_canvas_edit("hi", [{}], _canvas(), llm)


# ─────────── preservation: patch-first edits (Aug 31 regression) ───────────
# Real case: a narrow "update the email based on your findings" request made
# the editor regenerate the WHOLE draft from conversation memory, silently
# dropping the supervisor's manual on-canvas edits. Ops make preservation
# structural; the prompt makes the current content the authority; and
# send-requests ("try sending it again") must never land in the edit step.

def test_history_transcript_includes_agent_findings_and_skips_errors():
    from core.chat_canvas_editor import _history_transcript

    history = [
        {"message": "search the web for WFS Ltd",
         "response": {"message": "WFS Ltd is a dealer/distributor (a Grainger company)."}},
        {"message": "earlier failed turn",
         "response": {"message": "provider down"}, "error": True},
    ]
    out = _history_transcript(history, "update the draft based on your findings")
    assert "Agent: WFS Ltd is a dealer" in out      # findings are visible…
    assert "provider down" not in out               # …error turns never anchor
    assert "User: update the draft based on your findings" in out


@pytest.mark.asyncio
async def test_editor_prompt_demands_preservation_and_excludes_sends():
    llm = MagicMock()
    llm._get_handler.return_value.clients = {}
    llm.generate_structured_response = AsyncMock(return_value=CanvasEditPlan(wants_edit=False))
    await plan_canvas_edit("try sending it again", [], _canvas(), llm)
    prompt = llm.generate_structured_response.call_args.kwargs["prompt"]
    assert "MANUAL EDITS" in prompt                 # user edits outrank memory
    assert 'edit_mode="patch"' in prompt            # surgical by default
    assert "NOT edits" in prompt                    # sends route to the action step


@pytest.mark.asyncio
async def test_plan_prompt_carries_sender_identity_and_bans_cc_guessing():
    """Sender identity rides into the prompt as resolved data. Without it,
    "i added my signature, adjust" made the editor GUESS the sender's name
    from the Cc line — chandrakant@brennan.ca became the signature
    (observed live 2026-09-02, canvas da27bb76…)."""
    llm = MagicMock()
    llm._get_handler.return_value.clients = {}
    llm.generate_structured_response = AsyncMock(return_value=CanvasEditPlan(wants_edit=False))
    await plan_canvas_edit(
        "adjust my signature", [], _canvas(), llm,
        user_identity={"name": "Rish Maniar", "email": "rish@brennan.ca",
                       "signature": "Rish M.\nBrennan Machinery Inc."},
    )
    prompt = llm.generate_structured_response.call_args.kwargs["prompt"]
    assert "SENDER IDENTITY" in prompt
    assert "Rish Maniar" in prompt                 # the real sender is named…
    assert "RECIPIENTS" in prompt                  # …and the To/Cc guess ban is stated
    assert "Brennan Machinery Inc." in prompt      # default signature rides along


@pytest.mark.asyncio
async def test_plan_prompt_includes_recent_supervisor_corrections():
    """Corrections are the RLHF signal reaching the point of generation:
    AFTER (what the supervisor kept) is shown as the preferred wording."""
    llm = MagicMock()
    llm._get_handler.return_value.clients = {}
    llm.generate_structured_response = AsyncMock(return_value=CanvasEditPlan(wants_edit=True))
    corrections = [{
        "original": {"type": "canvas_edit", "content": "Are you an end user?", "author": "agent"},
        "corrected": {"type": "canvas_edit", "content": "Do you stock the 115C line?", "author": "supervisor"},
    }]
    await plan_canvas_edit(
        "update the question", [], _canvas(content="Draft body"), llm,
        corrections=corrections,
    )
    prompt = llm.generate_structured_response.call_args.kwargs["prompt"]
    assert "supervisor corrections" in prompt
    assert "Are you an end user?" in prompt         # BEFORE
    assert "Do you stock the 115C line?" in prompt  # AFTER
    assert "never revert it" in prompt


@pytest.mark.asyncio
async def test_plan_prompt_omits_corrections_section_when_empty():
    llm = MagicMock()
    llm._get_handler.return_value.clients = {}
    llm.generate_structured_response = AsyncMock(return_value=CanvasEditPlan(wants_edit=True))
    await plan_canvas_edit("edit", [], _canvas(), llm, corrections=[])
    prompt = llm.generate_structured_response.call_args.kwargs["prompt"]
    assert "supervisor corrections" not in prompt


def test_corrections_section_bounds_huge_entries():
    from core.chat_canvas_editor import _corrections_section
    huge = "x" * 5000
    out = _corrections_section([{
        "original": {"content": huge},
        "corrected": {"content": huge},
    }])
    assert len(out) < 1200  # per-entry bound keeps the structured call cheap


@pytest.mark.asyncio
async def test_patch_ops_match_is_validated_against_current_content():
    llm = MagicMock()
    llm._get_handler.return_value.clients = {}
    plan = CanvasEditPlan(
        wants_edit=True, edit_mode="patch",
        ops=[CanvasPatchOp(find="stocking the 115C?", replace="carrying the 115C line?")],
    )
    llm.generate_structured_response = AsyncMock(return_value=plan)
    content = "Hi Mark,\n\nAre you stocking the 115C?\n\nBest regards,"
    p = await plan_canvas_edit("tighten the question", [], _canvas(content=content), llm)
    assert p is not None and p.ops
    llm.generate_structured_response.assert_awaited_once()  # no re-ask needed


@pytest.mark.asyncio
async def test_failed_patch_ops_get_one_replace_mode_reask():
    llm = MagicMock()
    llm._get_handler.return_value.clients = {}
    bad = CanvasEditPlan(wants_edit=True, ops=[CanvasPatchOp(find="NOT PRESENT", replace="x")])
    rescued = CanvasEditPlan(wants_edit=True, updated_content_json='"full new text"')
    llm.generate_structured_response = AsyncMock(side_effect=[bad, rescued])
    p = await plan_canvas_edit("update the price line", [], _canvas(content="current"), llm)
    assert p is rescued
    assert llm.generate_structured_response.await_count == 2
    reask_prompt = llm.generate_structured_response.await_args_list[1].kwargs["prompt"]
    # The re-ask is field-scoped now (merge on apply) — it no longer demands
    # a byte-identical echo of untouched content ("IDENTICAL" era), which was
    # the burden that made small models emit oversized invalid JSON.
    assert "did not match" in reask_prompt
    assert "ONLY the keys you are changing" in reask_prompt


@pytest.mark.asyncio
async def test_double_failed_patch_plan_returns_none():
    llm = MagicMock()
    llm._get_handler.return_value.clients = {}
    bad1 = CanvasEditPlan(wants_edit=True, ops=[CanvasPatchOp(find="NOPE", replace="x")])
    bad2 = CanvasEditPlan(wants_edit=True, ops=[CanvasPatchOp(find="ALSO NOPE", replace="y")])
    llm.generate_structured_response = AsyncMock(side_effect=[bad1, bad2])
    # No salvageable plan → conversation path; a guessed write is worse.
    assert await plan_canvas_edit("edit it", [], _canvas(content="current"), llm) is None


@pytest.mark.asyncio
async def test_apply_patch_preserves_untouched_bytes():
    content = "Hi Mark,\n\nWe discussed the 115C.\n\nBest regards,\nAlex"
    plan = CanvasEditPlan(
        wants_edit=True,
        ops=[CanvasPatchOp(find="We discussed the 115C.",
                           replace="We discussed the 115C bandsaw quote.")],
    )
    with patch("tools.canvas_crud_tool.update_canvas_content", new=AsyncMock(
        return_value={"success": True}
    )) as upd:
        result = await apply_canvas_edit(plan, "user-1", _canvas(content=content))
    assert result and result["success"]
    assert upd.await_args.args[2] == (
        "Hi Mark,\n\nWe discussed the 115C bandsaw quote.\n\nBest regards,\nAlex"
    )


@pytest.mark.asyncio
async def test_apply_patch_edits_only_the_named_field_of_object_content():
    content = {
        "to": "mkellam@wfsltd.ca", "cc": "dng@wfsltd.ca",
        "subject": "Re: Baxter 115C",
        "body": "Hi Mark,\n\nAre you stocking the 115C?\n\nBest regards,\nAlex",
    }
    plan = CanvasEditPlan(
        wants_edit=True,
        ops=[CanvasPatchOp(field="body", find="Are you stocking the 115C?",
                           replace="As a Grainger dealer, do you carry the 115C line?")],
    )
    with patch("tools.canvas_crud_tool.update_canvas_content", new=AsyncMock(
        return_value={"success": True}
    )) as upd:
        result = await apply_canvas_edit(plan, "user-1", _canvas(content=content))
    assert result and result["success"]
    out = upd.await_args.args[2]
    assert "Grainger dealer" in out["body"]
    assert "stocking" not in out["body"]
    # Untouched keys are the SAME objects/bytes — a field-targeted op can't
    # drift them the way whole-content regeneration did.
    assert out["to"] == content["to"] and out["cc"] == content["cc"]
    assert out["subject"] == content["subject"]


@pytest.mark.asyncio
async def test_apply_refuses_patch_when_content_moved_under_the_plan():
    plan = CanvasEditPlan(wants_edit=True, ops=[CanvasPatchOp(find="old", replace="new")])
    with patch("tools.canvas_crud_tool.update_canvas_content", new=AsyncMock()) as upd:
        assert await apply_canvas_edit(plan, "user-1", _canvas(content="different")) is None
    upd.assert_not_awaited()


@pytest.mark.asyncio
async def test_apply_detects_noop_and_skips_the_write():
    """A plan that reproduces the current content byte-for-byte writes
    nothing and reports "no_change". Live incident (2026-09-02, canvas
    da27bb76…): "mark is the dealer and not end user" produced a
    byte-identical audit row while the reply still claimed "I have updated
    the email body…" — the user read that as the agent lying ("nothing
    changed")."""
    plan = CanvasEditPlan(wants_edit=True, ops=[CanvasPatchOp(find="Hello", replace="Hello")])
    with patch("tools.canvas_crud_tool.update_canvas_content", new=AsyncMock()) as upd:
        result, reason = await apply_canvas_edit(
            plan, "user-1", _canvas(content="Hello"), return_reason=True,
        )
    assert result is None and reason == "no_change"
    upd.assert_not_awaited()


def test_describe_apply_failure_no_change_reads_honestly():
    from core.chat_canvas_editor import describe_apply_failure

    msg = describe_apply_failure("no_change", "email", _canvas())
    assert "already reflects" in msg
    assert "nothing" in msg.lower()


# ───────────── grid patch ops: sheets as first-class canvases ─────────────

def test_patch_ops_edit_one_cell_of_rows_grid():
    content = {"rows": [["Item", "Qty"], ["115C", "1"], ["Blade", "3"]], "title": "Quote"}
    plan = CanvasEditPlan(wants_edit=True, ops=[
        CanvasPatchOp(cell="B3", find="3", replace="5"),
    ])
    out, failed = _apply_patch_ops(content, plan.ops)
    assert not failed
    assert out["rows"][2][1] == "5"
    assert out["rows"][0] == ["Item", "Qty"]          # untouched rows identical
    assert out["rows"][1] == ["115C", "1"]
    assert out["title"] == content["title"]


def test_patch_ops_edit_bare_list_grid_and_cells_dict():
    bare = [["Item", "Qty"], ["115C", "1"]]
    out, failed = _apply_patch_ops(bare, [CanvasPatchOp(cell="A2", find="115C", replace="Baxter 115C")])
    assert not failed and out[1][0] == "Baxter 115C" and out[0] == ["Item", "Qty"]

    cells = {"cells": {"A1": {"cell_ref": "A1", "value": "old"}, "B1": {"cell_ref": "B1", "value": "keep"}}}
    out2, failed2 = _apply_patch_ops(cells, [CanvasPatchOp(cell="A1", find="old", replace="new")])
    assert not failed2
    assert out2["cells"]["A1"]["value"] == "new"
    assert out2["cells"]["B1"] == cells["cells"]["B1"]  # identity preserved


def test_patch_ops_cell_mismatch_fails_that_op_only():
    content = [["a", "b"]]
    out, failed = _apply_patch_ops(content, [
        CanvasPatchOp(cell="A1", find="a", replace="x"),
        CanvasPatchOp(cell="B1", find="WRONG", replace="y"),
        CanvasPatchOp(cell="ZZZ99", find="a", replace="z"),   # bad ref
    ])
    assert len(failed) == 2
    assert out[0] == ["x", "b"]


@pytest.mark.asyncio
async def test_plan_validation_routes_grid_mismatch_to_replace_reask():
    llm = MagicMock()
    llm._get_handler.return_value.clients = {}
    bad = CanvasEditPlan(wants_edit=True, ops=[CanvasPatchOp(cell="B1", find="NOPE", replace="y")])
    rescued = CanvasEditPlan(wants_edit=True, updated_content_json='{"rows": [["a", "y"]]}')
    llm.generate_structured_response = AsyncMock(side_effect=[bad, rescued])
    p = await plan_canvas_edit("update the cell", [], _canvas(content={"rows": [["a", "b"]]}), llm)
    assert p is rescued


# ───────────── orchestrator: plan against the durable store ─────────────

@pytest.mark.asyncio
async def test_canvas_edit_plans_against_durable_store_content():
    """The panel can send stale canvas_content (missed broadcast, autosave
    window). Planning must read the latest audit row — a plan built on stale
    content is what silently reverted the supervisor's saved edits."""
    orch = _orch()
    plan = CanvasEditPlan(wants_edit=True, updated_content_json='"new"', reply="ok")
    seen = {}

    async def fake_plan(message, history, canvas, llm, corrections=None, versions=None, lessons=None, similar_corrections=None, correction_patterns=None, provenance=None, user_identity=None, playbooks=None):
        seen["content"] = canvas.get("content")
        return plan

    with patch.object(orch, "_record_chat_step", new=AsyncMock()), \
         patch("tools.canvas_crud_tool.read_canvas", new=AsyncMock(return_value={
             "success": True, "canvas_id": "c-123", "canvas_type": "email",
             "title": "T", "content": {"body": "fresh DB body"}})), \
         patch("core.chat_canvas_editor.plan_canvas_edit", new=AsyncMock(side_effect=fake_plan)), \
         patch("core.chat_canvas_editor.apply_canvas_edit", new=AsyncMock(
             return_value={"success": True})):
        resp = await orch._try_canvas_edit(
            "update it", [],
            {"canvas_id": "c-123", "canvas_type": "email", "title": "stale",
             "content": "stale client body"},
            "user-1", "s-1", "exec-1", None,
        )
    assert resp and resp["success"]
    assert seen["content"] == {"body": "fresh DB body"}


@pytest.mark.asyncio
async def test_canvas_edit_passes_supervisor_corrections_to_planner():
    """The edits the supervisor made ON the canvas are the training signal
    ("fix it here and I'll learn"). Recording them feeds maturity; the edit
    plan must ALSO see them, or the next draft repeats the corrected mistake."""
    orch = _orch()
    plan = CanvasEditPlan(wants_edit=True, updated_content_json='"new"', reply="ok")
    seen = {}

    async def fake_plan(message, history, canvas, llm, corrections=None, versions=None, lessons=None, similar_corrections=None, correction_patterns=None, provenance=None, user_identity=None, playbooks=None):
        seen["corrections"] = corrections
        return plan

    ctx_row = MagicMock()
    ctx_row.user_corrections = [
        {"original": {"content": "Are you an end user?", "author": "agent"},
         "corrected": {"content": "Do you stock the 115C line?", "author": "supervisor"}},
    ]
    ctx_svc = MagicMock()
    ctx_svc.get_context.return_value = ctx_row

    with patch.object(orch, "_record_chat_step", new=AsyncMock()), \
         patch("core.chat_canvas_editor.plan_canvas_edit", new=AsyncMock(side_effect=fake_plan)), \
         patch("core.chat_canvas_editor.apply_canvas_edit", new=AsyncMock(
             return_value={"success": True})), \
         patch("core.service_factory.ServiceFactory.get_canvas_context_service",
               return_value=ctx_svc):
        resp = await orch._try_canvas_edit(
            "tighten it", [], _canvas(), "user-1", "s-1", "exec-1", "hire-1",
        )
    assert resp and resp["success"]
    assert seen["corrections"] == ctx_row.user_corrections
    ctx_svc.get_context.assert_called_once_with("c-123", "user-1")


@pytest.mark.asyncio
async def test_canvas_edit_survives_corrections_lookup_failure():
    """No context row / DB down → empty corrections, the edit still runs."""
    orch = _orch()
    plan = CanvasEditPlan(wants_edit=True, updated_content_json='"new"', reply="ok")
    seen = {}

    async def fake_plan(message, history, canvas, llm, corrections=None, versions=None, lessons=None, similar_corrections=None, correction_patterns=None, provenance=None, user_identity=None, playbooks=None):
        seen["corrections"] = corrections
        return plan

    with patch.object(orch, "_record_chat_step", new=AsyncMock()), \
         patch("core.chat_canvas_editor.plan_canvas_edit", new=AsyncMock(side_effect=fake_plan)), \
         patch("core.chat_canvas_editor.apply_canvas_edit", new=AsyncMock(
             return_value={"success": True})), \
         patch("core.database.get_db_session", side_effect=RuntimeError("db down")):
        resp = await orch._try_canvas_edit(
            "tighten it", [], _canvas(), "user-1", "s-1", "exec-1", "hire-1",
        )
    assert resp and resp["success"]
    assert seen["corrections"] == []


@pytest.mark.asyncio
async def test_canvas_action_plans_against_durable_store_content():
    """A send planned from the panel's stale content would dispatch an
    out-of-date draft — actions read the store first too."""
    import contextlib

    from core.autonomy_policy import MODE_HUMAN_ALWAYS
    from core.chat_canvas_editor import CanvasActionPlan

    orch = _orch()
    plan = CanvasActionPlan(wants_action=True, action="send_email",
                            to="m@x", reply="r")
    seen = {}

    async def fake_plan(message, history, canvas, llm, playbooks=None):
        seen["content"] = canvas.get("content")
        return plan

    @contextlib.contextmanager
    def db_session():
        yield MagicMock()

    with patch.object(orch, "_record_chat_step", new=AsyncMock()), \
         patch("tools.canvas_crud_tool.read_canvas", new=AsyncMock(return_value={
             "success": True, "canvas_id": "c-123", "canvas_type": "email",
             "title": "T", "content": {"body": "fresh DB body"}})), \
         patch("core.chat_canvas_editor.plan_canvas_action", new=AsyncMock(side_effect=fake_plan)), \
         patch("core.autonomy_policy.get_effective_mode", return_value=MODE_HUMAN_ALWAYS), \
         patch("core.database.get_db_session", side_effect=lambda: db_session()), \
         patch.object(orch, "_create_send_email_proposal", return_value="prop-x"):
        resp = await orch._try_canvas_action(
            "send it", [],
            {"canvas_id": "c-123", "canvas_type": "email", "title": "stale",
             "content": "stale client body"},
            "user-1", "s-1", "exec-1", "hire-1",
        )
    assert resp and resp["data"]["canvas_action"]["needs_approval"] is True
    assert seen["content"] == {"body": "fresh DB body"}


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
async def test_canvas_edit_planning_failure_replies_honestly():
    """Plan-step LLM failure must NOT fall through to conversation: the
    intent router misfiles edit-shaped requests into TASK_MANAGEMENT and the
    reply claims a change the canvas never received (observed live Aug 31,
    2026 — "append LIVEUPDATEcheck456" answered with fabricated success)."""
    from core.chat_canvas_editor import CanvasPlanUnavailable

    orch = _orch()
    with patch.object(orch, "_record_chat_step", new=AsyncMock()), \
         patch("core.chat_canvas_editor.plan_canvas_edit", new=AsyncMock(
             side_effect=CanvasPlanUnavailable("provider down"))):
        resp = await orch._try_canvas_edit(
            "append this exact line at the very end of the email body: X",
            [], _canvas(), "user-1", "s-1", "exec-1", None,
        )
    assert resp is not None and resp["success"]
    assert resp["data"]["canvas_edit"]["updated"] is False
    assert resp["data"]["canvas_edit"]["plan_unavailable"] is True
    assert "nothing was changed" in resp["message"]


@pytest.mark.asyncio
async def test_canvas_edit_replies_honestly_on_noop():
    """A no-op edit (planned content == current content) must answer
    "nothing needed changing". Writing an identical audit row and claiming
    success read as the agent lying — the user repeated the same feedback
    three turns in a row while the canvas never moved (observed live
    2026-09-02, canvas da27bb76…)."""
    orch = _orch()
    with patch.object(orch, "_record_chat_step", new=AsyncMock()), \
         patch.object(orch, "_sender_identity", new=AsyncMock(return_value=None)), \
         patch("core.chat_canvas_editor.plan_canvas_edit", new=AsyncMock(
             return_value=CanvasEditPlan(wants_edit=True,
                                         updated_content_json='"x"', reply="done"))), \
         patch("core.chat_canvas_editor.apply_canvas_edit", new=AsyncMock(
             return_value=(None, "no_change"))):
        resp = await orch._try_canvas_edit(
            "mark is the dealer and not end user", [], _canvas(),
            "user-1", "s-1", "exec-1", "hire-1",
        )
    assert resp and resp["success"]
    assert "already reflects" in resp["message"]
    assert resp["data"]["canvas_edit"]["updated"] is False
    assert resp["data"]["canvas_edit"]["no_change"] is True


@pytest.mark.asyncio
async def test_canvas_edit_passes_sender_identity_to_planner():
    """The orchestrator resolves the sender (account + default signature)
    and hands it to the edit planner — identity is data, never a model
    guess from the To/Cc fields."""
    orch = _orch()
    plan = CanvasEditPlan(wants_edit=True, updated_content_json='"new"', reply="ok")
    seen = {}

    async def fake_plan(message, history, canvas, llm, corrections=None, versions=None,
                        lessons=None, similar_corrections=None, correction_patterns=None,
                        provenance=None, user_identity=None, playbooks=None):
        seen["identity"] = user_identity
        return plan

    with patch.object(orch, "_record_chat_step", new=AsyncMock()), \
         patch.object(orch, "_sender_identity", new=AsyncMock(
             return_value={"name": "Rish Maniar", "email": "rish@brennan.ca"})), \
         patch("core.chat_canvas_editor.plan_canvas_edit", new=AsyncMock(side_effect=fake_plan)), \
         patch("core.chat_canvas_editor.apply_canvas_edit", new=AsyncMock(
             return_value={"success": True})):
        await orch._try_canvas_edit(
            "adjust the signature", [], _canvas(), "user-1", "s-1", "exec-1", "hire-1",
        )
    assert seen["identity"] == {"name": "Rish Maniar", "email": "rish@brennan.ca"}


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
async def test_human_always_edit_policy_forces_proposal_even_for_mature_hire():
    """The owner's canvas_edit=human_always must bite on the EDIT path too
    (previously only sends consulted the policy — the Autonomy tab promised
    'always require me' while a mature hire applied edits unilaterally).
    A mature hire under human_always still drafts the proposal, but the
    reply is approval-voiced (not student-voiced) and the history records
    the policy reason."""
    from core.autonomy_policy import MODE_HUMAN_ALWAYS

    orch = _orch()
    plan = CanvasEditPlan(
        wants_edit=True,
        updated_content_json=json.dumps({"type": "doc", "content": "Final"}),
        reply="Done.",
    )
    gov = MagicMock()
    gov.can_perform_action.return_value = {"allowed": True}  # mature enough
    ctx_svc = MagicMock()
    with patch.object(orch, "_record_chat_step", new=AsyncMock()), \
         patch("core.chat_canvas_editor.plan_canvas_edit", new=AsyncMock(return_value=plan)), \
         patch("core.chat_canvas_editor.apply_canvas_edit", new=AsyncMock(
             return_value={"success": True})), \
         patch("core.autonomy_policy.get_effective_mode", return_value=MODE_HUMAN_ALWAYS), \
         patch("core.service_factory.ServiceFactory.get_governance_service", return_value=gov), \
         patch("core.service_factory.ServiceFactory.get_canvas_context_service", return_value=ctx_svc):
        resp = await orch._try_canvas_edit(
            "tighten the draft", [], _canvas(), "user-1", "s-1", "exec-1", "hire-1",
        )

    assert resp and resp["success"]
    assert resp["data"]["canvas_edit"]["learning_mode"] is True
    assert "autonomy setting" in resp["message"]       # policy voice…
    assert "still learning" not in resp["message"]     # …not student voice
    recorded = ctx_svc.add_action_to_history.call_args.kwargs["action"]
    assert recorded["type"] == "canvas_edit_proposal"
    assert recorded["human_always"] is True
    assert recorded["learning_mode"] is False          # mature hire, policy-gated


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
async def test_send_action_executes_when_autonomous_mature_and_allowlisted(monkeypatch):
    """Autonomy + maturity + an ALLOWLISTED recipient (email policy = allow)
    → direct execution. Regression context: agent-initiated sends to
    EXTERNAL recipients used to bypass the email policy's human-approval
    requirement on this path and go straight to transport (observed
    2026-08-31); the gate now fires BEFORE execution."""
    import contextlib
    from core.autonomy_policy import MODE_AUTO_IF_MATURE
    from core.chat_canvas_editor import CanvasActionPlan

    monkeypatch.setenv("ATOM_EMAIL_ALLOWED_OUTBOUND_DOMAINS", "example.com")
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
         })) as exec_mock, \
         patch.object(orch, "_create_send_email_proposal", return_value="prop-x") as prop_mock:
        resp = await orch._try_canvas_action(
            "send this to mark@example.com", [], _canvas(), "user-1", "s-1", "exec-1", "hire-1",
        )

    assert resp and resp["intent"] == "canvas_action"
    assert "sent" in resp["message"].lower()
    exec_mock.assert_awaited_once()
    prop_mock.assert_not_called()


@pytest.mark.asyncio
async def test_send_action_proposes_when_trust_below_bar(monkeypatch):
    """Skill-scoped trust (R8) gates sends too: policy auto + maturity ok
    but a low VERIFIED trust score → propose, never transport."""
    import contextlib
    from core.autonomy_policy import MODE_AUTO_IF_MATURE
    from core.chat_canvas_editor import CanvasActionPlan

    monkeypatch.setenv("ATOM_EMAIL_ALLOWED_OUTBOUND_DOMAINS", "example.com")
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
         patch("core.autonomy_policy.trust_check", return_value={
             "enabled": True, "trust": 0.2, "threshold": 0.6,
             "cold_start": False, "ok": False}), \
         patch("core.service_factory.ServiceFactory.get_governance_service", return_value=gov), \
         patch("core.database.get_db_session", side_effect=lambda: db_session()), \
         patch.object(orch, "_execute_send_email", new=AsyncMock()) as exec_mock, \
         patch.object(orch, "_create_send_email_proposal", return_value="prop-t") as prop_mock:
        resp = await orch._try_canvas_action(
            "send this to mark@example.com", [], _canvas(), "user-1", "s-1", "exec-1", "hire-1",
        )

    assert resp and resp["data"]["canvas_action"]["needs_approval"] is True
    assert resp["data"]["canvas_action"]["proposal_id"] == "prop-t"
    assert "trust" in resp["message"].lower()
    exec_mock.assert_not_awaited()
    prop_mock.assert_called_once()


@pytest.mark.asyncio
async def test_send_action_proposes_for_external_recipient_even_when_mature(monkeypatch):
    """The email policy's APPROVE (external recipient) ALWAYS requires a
    human — even for an autonomous, mature hire on auto-if-mature mode.
    Before the 2026-08-31 fix the agent path went straight to transport
    and would have dispatched unapproved whenever the transport worked."""
    import contextlib
    from core.autonomy_policy import MODE_AUTO_IF_MATURE
    from core.chat_canvas_editor import CanvasActionPlan

    monkeypatch.setenv("ATOM_EMAIL_ALLOWED_OUTBOUND_DOMAINS", "internal.example")
    orch = _orch()
    plan = CanvasActionPlan(
        wants_action=True, action="send_email", to="mark@external.test",
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
         patch.object(orch, "_execute_send_email", new=AsyncMock()) as exec_mock, \
         patch.object(orch, "_create_send_email_proposal", return_value="prop-1") as prop_mock:
        resp = await orch._try_canvas_action(
            "send this to mark@external.test", [], _canvas(), "user-1", "s-1", "exec-1", "hire-1",
        )

    assert resp and resp["success"] is True
    assert resp["data"]["canvas_action"]["needs_approval"] is True
    assert resp["data"]["canvas_action"]["proposal_id"] == "prop-1"
    exec_mock.assert_not_awaited()
    prop_mock.assert_called_once()


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


# ---------------------------------------------------------------------------
# RECENT VERSIONS — the go-back/restore path (audit trail → planner prompt)
# ---------------------------------------------------------------------------

def test_versions_section_renders_skips_current_and_trims():
    from core.chat_canvas_editor import _versions_section
    versions = [
        {"audit_id": "a3", "created_at": "2026-08-31T13:21:02", "actor": "agent",
         "title": "Dealer intro", "content": "x" * 2000},
        {"audit_id": "a2", "created_at": "2026-08-31T12:22:17", "actor": "supervisor",
         "content": "original supervisor wording"},
        {"audit_id": "a1", "created_at": "2026-08-31T12:20:00", "actor": "agent",
         "content": "current body"},  # == current content → dropped
    ]
    out = _versions_section(versions, "current body")
    assert "RECENT VERSIONS" in out
    assert 'edit_mode="restore"' in out          # the restore contract (by version_id)
    assert 'edit_mode="replace"' in out          # the fallback when no version_id is shown
    assert "version_id: a3" in out               # the id the restore names
    assert "version_id: a2" in out
    assert "Never invent a version_id" in out
    assert "original supervisor wording" in out
    assert "supervisor" in out and "agent" in out
    assert "x" * 2000 not in out                # trimmed to the per-version budget
    assert "current body" not in out            # the current-content version is dropped


def test_versions_section_empty_when_nothing_restorable():
    from core.chat_canvas_editor import _versions_section
    assert _versions_section(None, "body") == ""
    assert _versions_section([], "body") == ""
    # every version equals the current content → nothing to show
    assert _versions_section([{"content": "same"}], "same") == ""


@pytest.mark.asyncio
async def test_plan_prompt_includes_recent_versions_with_restore_rule():
    llm = MagicMock()
    llm._get_handler.return_value.clients = {}
    llm.generate_structured_response = AsyncMock(return_value=CanvasEditPlan(wants_edit=True))
    versions = [{
        "audit_id": "a2", "created_at": "2026-08-31T12:22:17",
        "actor": "supervisor", "content": "the ORIGINAL draft",
    }]
    await plan_canvas_edit(
        "go back to my original draft", [], _canvas(content="overwritten"), llm,
        versions=versions,
    )
    prompt = llm.generate_structured_response.call_args.kwargs["prompt"]
    assert "RECENT VERSIONS" in prompt
    assert "the ORIGINAL draft" in prompt
    assert "Never invent text for a version" in prompt


@pytest.mark.asyncio
async def test_canvas_edit_passes_recent_versions_to_planner():
    """Earlier audit versions ride into the plan — the go-back/restore path
    that was impossible when the agent could only see the latest content."""
    orch = _orch()
    plan = CanvasEditPlan(wants_edit=True, updated_content_json='"new"', reply="ok")
    seen = {}
    versions = [{"audit_id": "a-9", "content": "old draft", "actor": "supervisor"}]

    async def fake_plan(message, history, canvas, llm, corrections=None, versions=None, lessons=None, similar_corrections=None, correction_patterns=None, provenance=None, user_identity=None, playbooks=None):
        seen["versions"] = versions
        return plan

    with patch.object(orch, "_record_chat_step", new=AsyncMock()), \
         patch.object(orch, "_recent_canvas_versions", return_value=versions), \
         patch("core.chat_canvas_editor.plan_canvas_edit", new=AsyncMock(side_effect=fake_plan)), \
         patch("core.chat_canvas_editor.apply_canvas_edit", new=AsyncMock(
             return_value={"success": True})):
        resp = await orch._try_canvas_edit(
            "restore my previous draft", [], _canvas(), "user-1", "s-1", "exec-1", None,
        )
    assert resp and resp["success"]
    assert seen["versions"] == versions


# ─────────── "update the canvas" regression (Aug 31, live) ───────────
# The agent showed a simplified draft in chat; the user said "update the
# canvas". The planner truncated that reply to 300 chars ("We car…"), the
# model refused to apply a draft it couldn't read, and a degenerate
# replace plan (wants_edit=true, no ops, no content) sailed into apply just
# to be discarded — the user got "couldn't apply it cleanly".

def test_history_transcript_gives_last_agent_reply_full_budget():
    from core.chat_canvas_editor import _history_transcript

    full_draft = "Here's the simplified quote-request draft:\n\n" + "x" * 2000
    history = [
        {"message": "make it simpler", "response": {"message": "older reply " + "y" * 500}},
        {"message": "update the canvas", "response": {"message": full_draft}},
    ]
    out = _history_transcript(history, "update the canvas")
    assert ("x" * 2000) in out                       # the applicable draft is fully visible
    assert ("y" * 400) not in out                    # older replies capped at 300 chars
    assert "…(trimmed)" in out                       # trimming is explicit


@pytest.mark.asyncio
async def test_degenerate_replace_plan_reasks_instead_of_reaching_apply():
    """wants_edit=true with no ops and no content must not sail into apply
    (where it was discarded as "not valid JSON") — it gets the same one
    replace-mode re-ask as failed patch ops."""
    llm = MagicMock()
    llm._get_handler.return_value.clients = {}
    degenerate = CanvasEditPlan(wants_edit=True, edit_mode="replace",
                                updated_content_json=None, reply="")
    recovered = CanvasEditPlan(wants_edit=True, edit_mode="replace",
                               updated_content_json='{"to": "a@b.c", "subject": "S", "body": "B"}',
                               reply="applied")
    llm.generate_structured_response = AsyncMock(side_effect=[degenerate, recovered])

    p = await plan_canvas_edit("update the canvas", [], _canvas(content={"to": "", "subject": "", "body": ""}), llm)

    assert p is recovered
    assert llm.generate_structured_response.await_count == 2
    reask_prompt = llm.generate_structured_response.call_args_list[1].kwargs["prompt"]
    # Field-scoped contract (see test_failed_patch_ops_get_one_replace_mode_reask).
    assert "REPLACE_FALLBACK" in reask_prompt or "ONLY THE KEYS YOU ARE CHANGING" in reask_prompt.upper()


@pytest.mark.asyncio
async def test_degenerate_replace_plan_still_empty_returns_none():
    llm = MagicMock()
    llm._get_handler.return_value.clients = {}
    degenerate = CanvasEditPlan(wants_edit=True, edit_mode="replace", updated_content_json=None)
    llm.generate_structured_response = AsyncMock(return_value=degenerate)

    p = await plan_canvas_edit("update the canvas", [], _canvas(content="body"), llm)
    assert p is None  # conversational clarification beats a fake "edit attempted"


# ─────────────────── taught lessons at edit time ───────────────────

@pytest.mark.asyncio
async def test_plan_prompt_includes_taught_lessons():
    """Lessons taught via /teach are PERMANENT training: the edit planner must
    see them at work time (all agents, all canvas apps) — storage alone only
    moved a confidence score."""
    llm = MagicMock()
    llm._get_handler.return_value.clients = {}
    llm.generate_structured_response = AsyncMock(return_value=CanvasEditPlan(wants_edit=True))
    lessons = [
        {"source": "teacher", "topic": "tone",
         "lesson": "Address the client as Dr. Reyes, never by first name",
         "learned_at": "2026-08-01T00:00:00+00:00"},
    ]
    await plan_canvas_edit(
        "update the greeting", [], _canvas(content="Hello"), llm,
        lessons=lessons,
    )
    prompt = llm.generate_structured_response.call_args.kwargs["prompt"]
    assert "TRAINING LESSONS" in prompt
    assert "PERMANENT INSTRUCTIONS" in prompt
    assert "Dr. Reyes" in prompt
    # the section binds the lessons to the preservation duty
    assert "preservation rules" in prompt


@pytest.mark.asyncio
async def test_plan_prompt_omits_lessons_section_when_empty():
    llm = MagicMock()
    llm._get_handler.return_value.clients = {}
    llm.generate_structured_response = AsyncMock(return_value=CanvasEditPlan(wants_edit=True))
    await plan_canvas_edit("edit", [], _canvas(), llm, lessons=[])
    prompt = llm.generate_structured_response.call_args.kwargs["prompt"]
    assert "TRAINING LESSONS" not in prompt


@pytest.mark.asyncio
async def test_plan_lessons_section_survives_renderer_failure():
    """A broken lessons renderer must never break the edit turn (fault
    isolation matches every other prompt section)."""
    llm = MagicMock()
    llm._get_handler.return_value.clients = {}
    llm.generate_structured_response = AsyncMock(return_value=CanvasEditPlan(
        wants_edit=True, updated_content_json='"new body"'))
    with patch("core.student_learning_service.format_lessons_block",
               side_effect=RuntimeError("boom")):
        plan = await plan_canvas_edit(
            "edit", [], _canvas(content="body"), llm,
            lessons=[{"source": "teacher", "lesson": "ignored"}],
        )
    assert plan is not None and plan.wants_edit


@pytest.mark.asyncio
async def test_canvas_edit_passes_taught_lessons_to_planner():
    """Orchestrator wiring: the hire's lessons reach plan_canvas_edit next to
    corrections and versions."""
    orch = _orch()
    plan = CanvasEditPlan(wants_edit=True, updated_content_json='"new"', reply="ok")
    seen = {}
    lessons = [{"source": "teacher", "topic": "tone", "lesson": "Formal register only",
                "learned_at": "2026-08-01T00:00:00+00:00"}]

    async def fake_plan(message, history, canvas, llm, corrections=None, versions=None, lessons=None, similar_corrections=None, correction_patterns=None, provenance=None, user_identity=None, playbooks=None):
        seen["lessons"] = lessons
        return plan

    with patch.object(orch, "_record_chat_step", new=AsyncMock()), \
         patch("core.chat_canvas_editor.plan_canvas_edit", new=AsyncMock(side_effect=fake_plan)), \
         patch("core.chat_canvas_editor.apply_canvas_edit", new=AsyncMock(
             return_value={"success": True})), \
         patch.object(orch, "_agent_lessons", return_value=lessons):
        resp = await orch._try_canvas_edit(
            "tighten it", [], _canvas(), "user-1", "s-1", "exec-1", "hire-1",
        )
    assert resp and resp["success"]
    assert seen["lessons"] == lessons


@pytest.mark.asyncio
async def test_canvas_edit_without_agent_passes_no_lessons():
    """Platform turns (no resolved hire) simply plan without lessons."""
    orch = _orch()
    plan = CanvasEditPlan(wants_edit=True, updated_content_json='"new"', reply="ok")
    seen = {}

    async def fake_plan(message, history, canvas, llm, corrections=None, versions=None, lessons=None, similar_corrections=None, correction_patterns=None, provenance=None, user_identity=None, playbooks=None):
        seen["lessons"] = lessons
        return plan

    with patch.object(orch, "_record_chat_step", new=AsyncMock()), \
         patch("core.chat_canvas_editor.plan_canvas_edit", new=AsyncMock(side_effect=fake_plan)), \
         patch("core.chat_canvas_editor.apply_canvas_edit", new=AsyncMock(
             return_value={"success": True})):
        resp = await orch._try_canvas_edit(
            "tighten it", [], _canvas(), "user-1", "s-1", "exec-1", None,
        )
    assert resp and resp["success"]
    assert seen["lessons"] == []


# ─────────────────── cc recipients through the send chain ───────────────────

@pytest.mark.asyncio
async def test_direct_agent_send_carries_cc(monkeypatch):
    """Autonomous + mature + allowlisted to/cc → direct send carries cc_emails
    (previously hardcoded [] — cc silently dropped on every agent send)."""
    import contextlib
    from core.autonomy_policy import MODE_AUTO_IF_MATURE
    from core.chat_canvas_editor import CanvasActionPlan

    monkeypatch.setenv("ATOM_EMAIL_ALLOWED_OUTBOUND_DOMAINS", "brennan.ca")
    orch = _orch()
    plan = CanvasActionPlan(
        wants_action=True, action="send_email", to="mark@brennan.ca",
        cc="vipul@brennan.ca, chandrakant@brennan.ca",
        subject="S", body="B", reply="Sending.",
    )
    gov = MagicMock()
    gov.can_perform_action.return_value = {"allowed": True}

    @contextlib.contextmanager
    def db_session():
        yield MagicMock()

    sent = {}
    class FakeEmailSvc:
        def __init__(self, db):
            pass
        async def send_email(self, **kw):
            sent.update(kw)
            return {"success": True, "status": "sent"}

    with patch.object(orch, "_record_chat_step", new=AsyncMock()), \
         patch("core.chat_canvas_editor.plan_canvas_action", new=AsyncMock(return_value=plan)), \
         patch("core.autonomy_policy.get_effective_mode", return_value=MODE_AUTO_IF_MATURE), \
         patch("core.service_factory.ServiceFactory.get_governance_service", return_value=gov), \
         patch("core.database.get_db_session", side_effect=lambda: db_session()), \
         patch("core.canvas_email_service.EmailCanvasService", FakeEmailSvc):
        resp = await orch._try_canvas_action(
            "send it", [], _canvas(), "user-1", "s-1", "exec-1", "hire-1",
        )

    assert resp and resp["success"]
    assert sent["cc_emails"] == ["vipul@brennan.ca", "chandrakant@brennan.ca"]


@pytest.mark.asyncio
async def test_send_proposal_carries_cc_from_canvas_fallback():
    """The proposal must carry cc (plan's, falling back to the canvas draft's
    cc field) — previously proposals had no cc at all, so approved sends
    went out with cc: [] (observed 2026-09-01)."""
    import contextlib
    from core.chat_canvas_editor import CanvasActionPlan

    orch = _orch()
    plan = CanvasActionPlan(
        wants_action=True, action="send_email", to="mark@external.test",
        subject="S", body="B",
    )
    canvas = _canvas(content={
        "to": "mark@external.test", "cc": "vipul@brennan.ca",
        "subject": "S", "body": "B",
    })
    captured = {}

    class FakeProposal:
        def __init__(self, **kw):
            captured.update(kw)
            self.id = "prop-cc-1"

    @contextlib.contextmanager
    def db_session():
        yield MagicMock()

    with patch("core.database.get_db_session", side_effect=lambda: db_session()), \
         patch("core.models.AgentProposal", side_effect=FakeProposal), \
         patch("core.models.AgentRegistry") as reg:
        reg.query.return_value.filter.return_value.first.return_value = None
        pid = orch._create_send_email_proposal(plan, canvas, "u-1", "s-1", "hire-1")

    assert pid == "prop-cc-1"
    assert captured["proposal_data"]["cc"] == "vipul@brennan.ca"


@pytest.mark.asyncio
async def test_approved_proposal_execution_sends_cc():
    """The Journey approve-and-send executor passes the proposal's cc through
    to EmailCanvasService (previously cc_emails=[] hardcoded)."""
    from types import SimpleNamespace
    from unittest.mock import MagicMock, patch

    from core.proposal_service import ProposalService
    svc = ProposalService(MagicMock())
    proposal = SimpleNamespace(id="p-1", user_id="u-1", agent_id="hire-1", canvas_id="c-1")
    action = {"to": "mark@external.test", "cc": "vipul@brennan.ca, chandrakant@brennan.ca",
              "subject": "S", "body": "B"}

    sent = {}
    class FakeEmailSvc:
        def __init__(self, db):
            pass
        async def send_email(self, **kw):
            sent.update(kw)
            return {"success": True, "status": "sent"}

    with patch("core.canvas_email_service.EmailCanvasService", FakeEmailSvc), \
         patch.object(svc, "_record_execution_episode") as ep_mock:
        out = await svc._execute_send_email_action(proposal, action)

    assert out["success"] is True
    assert sent["cc_emails"] == ["vipul@brennan.ca", "chandrakant@brennan.ca"]
    # The approved send is EXECUTION-BACKED evidence: an execution row is
    # completed and an episode recorded, so students on the co-editor flow
    # earn constitutional-measured work (not just chat-derived episodes).
    ep_mock.assert_called_once()
    execution, _proposal, action_type = ep_mock.call_args.args
    assert action_type == "send_email"
    assert execution.status == "completed"
    assert execution.agent_id == "hire-1"


@pytest.mark.asyncio
async def test_approved_proposal_send_refusal_still_records_failed_execution():
    """A policy-refused send records a FAILED execution episode — the
    supervisor sees honest evidence, not a silently missing run."""
    from types import SimpleNamespace
    from unittest.mock import MagicMock, patch

    from core.proposal_service import ProposalService
    svc = ProposalService(MagicMock())
    proposal = SimpleNamespace(id="p-2", user_id="u-1", agent_id="hire-1", canvas_id="c-1")
    action = {"to": "mark@external.test", "subject": "S", "body": "B"}

    class FakeEmailSvc:
        def __init__(self, db):
            pass
        async def send_email(self, **kw):
            return {"success": False, "error": "sensitivity block"}

    with patch("core.canvas_email_service.EmailCanvasService", FakeEmailSvc), \
         patch.object(svc, "_record_execution_episode") as ep_mock:
        out = await svc._execute_send_email_action(proposal, action)

    assert out["success"] is False
    ep_mock.assert_called_once()
    execution, _proposal, action_type = ep_mock.call_args.args
    assert action_type == "send_email"
    assert execution.status == "failed"


# ───────────────────────── restore mode (version revert) ─────────────────────────
# The recovery path: "go back to my earlier draft" restores an exact version
# by audit_id through the audit-trail restore — deterministic, lossless, and
# appended as a new version so the revert itself is revertable.

@pytest.mark.asyncio
async def test_apply_restore_routes_through_audit_trail_restore():
    plan = CanvasEditPlan(
        wants_edit=True,
        edit_mode="restore",
        restore_audit_id="a-42",
        reply="Restored your earlier draft.",
    )
    with patch("tools.canvas_crud_tool.restore_canvas_version", new=AsyncMock(
        return_value={"success": True, "restored_from": "a-42"}
    )) as restore:
        result = await apply_canvas_edit(plan, "user-1", _canvas())
    assert result and result["success"]
    restore.assert_awaited_once_with("user-1", "c-123", "a-42")


@pytest.mark.asyncio
async def test_apply_restore_without_explicit_mode_still_routes_by_id():
    # A model that sets restore_audit_id but forgets edit_mode still gets
    # the deterministic restore — the id is the intent.
    plan = CanvasEditPlan(wants_edit=True, restore_audit_id="a-7")
    with patch("tools.canvas_crud_tool.restore_canvas_version", new=AsyncMock(
        return_value={"success": True}
    )) as restore:
        result = await apply_canvas_edit(plan, "user-1", _canvas())
    assert result and result["success"]
    restore.assert_awaited_once()


@pytest.mark.asyncio
async def test_apply_restore_noop_reports_honestly():
    plan = CanvasEditPlan(wants_edit=True, edit_mode="restore", restore_audit_id="a-1")
    with patch("tools.canvas_crud_tool.restore_canvas_version", new=AsyncMock(
        return_value={"success": True, "no_change": True}
    )):
        result, reason = await apply_canvas_edit(
            plan, "user-1", _canvas(), return_reason=True)
    assert result is None
    assert reason == "no_change"


@pytest.mark.asyncio
async def test_apply_restore_unknown_version_maps_to_honest_reason():
    plan = CanvasEditPlan(wants_edit=True, edit_mode="restore", restore_audit_id="a-ghost")
    with patch("tools.canvas_crud_tool.restore_canvas_version", new=AsyncMock(
        return_value={"success": False, "error": "Version not found"}
    )):
        result, reason = await apply_canvas_edit(
            plan, "user-1", _canvas(), return_reason=True)
    assert result is None
    assert reason == "version_not_found"


def test_describe_apply_failure_version_not_found_is_actionable():
    from core.chat_canvas_editor import describe_apply_failure

    text = describe_apply_failure("version_not_found", "document")
    assert "Nothing was changed" in text


@pytest.mark.asyncio
async def test_restore_plan_with_version_id_needs_no_reask():
    llm = MagicMock()
    llm._get_handler.return_value.clients = {}
    plan = CanvasEditPlan(
        wants_edit=True, edit_mode="restore", restore_audit_id="a-9",
        reply="Going back to your first draft.",
    )
    llm.generate_structured_response = AsyncMock(return_value=plan)
    p = await plan_canvas_edit(
        "restore my original draft", [], _canvas(content="current text"), llm)
    assert p is plan
    llm.generate_structured_response.assert_awaited_once()  # no replace re-ask


@pytest.mark.asyncio
async def test_restore_plan_without_version_id_gets_one_reask():
    llm = MagicMock()
    llm._get_handler.return_value.clients = {}
    degenerate = CanvasEditPlan(wants_edit=True, edit_mode="restore")
    rescued = CanvasEditPlan(wants_edit=True, updated_content_json='"restored text"')
    llm.generate_structured_response = AsyncMock(side_effect=[degenerate, rescued])
    p = await plan_canvas_edit("go back", [], _canvas(content="current"), llm)
    assert p is rescued
    assert llm.generate_structured_response.await_count == 2


def test_versions_section_carries_version_ids():
    from core.chat_canvas_editor import _versions_section

    section = _versions_section(
        [{
            "audit_id": "a-123",
            "created_at": "2026-09-01T10:00:00",
            "actor": "supervisor",
            "title": "First draft",
            "content": "the original text",
        }],
        current="the edited text",
    )
    assert "version_id: a-123" in section
    assert "restore" in section.lower()
    assert "edit_mode=\"restore\"" in section


def test_versions_section_dropped_when_versions_match_current():
    from core.chat_canvas_editor import _versions_section

    section = _versions_section(
        [{
            "audit_id": "a-1", "created_at": "2026-09-01T10:00:00",
            "actor": "agent", "content": "same text",
        }],
        current="same text",
    )
    assert section == ""
