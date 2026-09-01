"""Per-app canvas co-editor fixes (Sep 1, 2026 — the "couldn't apply it
cleanly" incident, canvas 4c1986b1).

Root-cause chain pinned here, one test per gap:

1. Patch ops could not FILL AN EMPTY field (find="" always failed) — the
   "include to and cc emails as well" request was structurally impossible in
   patch mode and forced into the fragile full-content replace re-ask.
2. The replace re-ask demanded the whole ~1.7k-char HTML body re-emitted as
   valid JSON by a small pinned model; invalid JSON was discarded wholesale.
3. The seeded canvas itself was degenerate (empty To/Cc, truncated narration
   as Subject) — narration-tolerant extraction + a healing pass fix the seed.
4. Every canvas app now edits by ITS OWN schema (email fields, sheet grid,
   file-backed office snapshots) instead of one hardcoded email example.
"""
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.chat_canvas_editor import (
    CanvasEditPlan,
    CanvasPatchOp,
    _apply_patch_ops,
    _merge_replace_content,
    _repair_json,
    apply_canvas_edit,
    describe_apply_failure,
    normalize_degenerate_content,
    plan_canvas_edit,
)
from core.canvas_app_schema import (
    app_prompt_section,
    empty_fillable_fields,
    get_app_spec,
)

# The actual canvas content from the incident (chat-context payload, trimmed
# from the [CHATCTX] log line) — the fixture every heal/edit test replays.
LIVE_INCIDENT_CONTENT = {
    "to": "",
    "cc": "",
    "subject": "Draft — I found the email for Jacob Schulz from BluMetric. It looks",
    "body": (
        "I found the email for Jacob Schulz from BluMetric.<br><br>"
        "Here's the draft for the first contact email to Jacob Schulz:<br><br>---<br><br>"
        "**To:** jschulz@blumetric.ca<br>"
        "**Subject:** Brennan Machinery | Following Up on Your Inquiry<br><br>"
        "Hi Jacob,<br><br>Chandrakant here from Brennan Machinery. I received your "
        "contact form submission and wanted to reach out. Let us know about your "
        "equipment needs today.<br><br>Best,<br>Chandrakant Sharma<br>Brennan Machinery Inc"
    ),
}


def _email_canvas(content=None):
    return {
        "canvas_id": "c-123",
        "canvas_type": "email",
        "title": "Draft",
        "content": content if content is not None else dict(LIVE_INCIDENT_CONTENT),
    }


# ───────────────────────── set-field patch ops ─────────────────────────

def test_set_field_op_fills_empty_email_fields():
    ops = [
        CanvasPatchOp(field="to", find="", replace="jschulz@blumetric.ca"),
        CanvasPatchOp(field="cc", find="", replace="sales@brennan.ca"),
    ]
    new, failed = _apply_patch_ops(dict(LIVE_INCIDENT_CONTENT), ops)
    assert not failed
    assert new["to"] == "jschulz@blumetric.ca"
    assert new["cc"] == "sales@brennan.ca"
    # untouched keys keep identity
    assert new["subject"] == LIVE_INCIDENT_CONTENT["subject"]
    assert new["body"] == LIVE_INCIDENT_CONTENT["body"]


def test_set_field_op_refuses_non_empty_field():
    ops = [CanvasPatchOp(field="subject", find="", replace="New subject")]
    new, failed = _apply_patch_ops(dict(LIVE_INCIDENT_CONTENT), ops)
    assert failed and new["subject"] == LIVE_INCIDENT_CONTENT["subject"]


def test_empty_find_on_string_canvas_is_a_failure():
    new, failed = _apply_patch_ops("plain text", [CanvasPatchOp(find="", replace="x")])
    assert failed and new == "plain text"


def test_whitespace_insensitive_second_tier_matches():
    text = "Dear Jacob,\n\n  Welcome   aboard —\n let's begin."
    new, failed = _apply_patch_ops(
        text, [CanvasPatchOp(find="Welcome aboard", replace="Greetings")]
    )
    assert not failed and "Greetings" in new


def test_whitespace_tier_never_matches_single_token_or_absent_text():
    new, failed = _apply_patch_ops(
        "hello world", [CanvasPatchOp(find="goodbye", replace="x")]
    )
    assert failed
    new2, failed2 = _apply_patch_ops(
        "hello world", [CanvasPatchOp(find="hello", replace="hi")]
    )
    assert not failed2 and new2 == "hi world"


# ───────────────────────── repair + merge (replace path) ─────────────────────────

def test_repair_json_recovers_unescaped_quote_payload():
    raw = '{"to": "a@b.c", "subject": "Hi, "said" the man}'
    parsed = _repair_json(raw)
    assert isinstance(parsed, dict) and parsed["to"] == "a@b.c"


def test_repair_json_recovers_fenced_and_trailing_comma_payloads():
    fenced = "```json\n{\"to\": \"a@b.c\",}\n```"
    assert _repair_json(fenced) == {"to": "a@b.c"}


def test_repair_json_returns_none_for_prose():
    assert _repair_json("I would set the To field to someone@example.com.") is None


def test_merge_preserves_omitted_keys_and_drops_unknown_ones():
    current = dict(LIVE_INCIDENT_CONTENT)
    merged, reason = _merge_replace_content(
        {"to": "jschulz@blumetric.ca", "bogus_field": 1}, current, "email"
    )
    assert reason is None
    assert merged["to"] == "jschulz@blumetric.ca"
    assert merged["subject"] == current["subject"]       # preserved
    assert merged["body"] == current["body"]             # preserved
    assert "bogus_field" not in merged


def test_merge_with_no_known_fields_fails_with_reason():
    merged, reason = _merge_replace_content({"bogus": 1}, dict(LIVE_INCIDENT_CONTENT), "email")
    assert merged is None
    assert reason == "replace payload carried none of this app's fields"


def test_merge_full_payload_equals_whole_replace():
    full = {"to": "a@b.c", "cc": "", "subject": "S", "body": "B"}
    merged, reason = _merge_replace_content(full, dict(LIVE_INCIDENT_CONTENT), "email")
    assert reason is None and merged == full


def test_grid_replace_stays_whole_for_version_restore():
    grid = {"rows": [["a", "b"]]}
    merged, reason = _merge_replace_content({"rows": [["x", "y"]]}, grid, "sheet")
    assert reason is None and merged == {"rows": [["x", "y"]]}


def test_string_whole_replace_and_content_wrapper_accept_unwrapped_text():
    assert _merge_replace_content("new", "old", "document") == ("new", None)
    assert _merge_replace_content("new", {"content": "old"}, "document") == (
        {"content": "new"}, None
    )


@pytest.mark.asyncio
async def test_apply_replace_merge_via_crud_layer():
    with patch("tools.canvas_crud_tool.update_canvas_content", new=AsyncMock(
            return_value={"success": True})) as upd:
        plan = CanvasEditPlan(
            wants_edit=True, edit_mode="replace",
            updated_content_json=json.dumps({"to": "jschulz@blumetric.ca"}),
            reply="filled To",
        )
        result = await apply_canvas_edit(plan, "user-1", _email_canvas())
    assert result and result["success"]
    written = upd.call_args.args[2]
    assert written["to"] == "jschulz@blumetric.ca"
    assert written["body"] == LIVE_INCIDENT_CONTENT["body"]  # merged, not replaced


@pytest.mark.asyncio
async def test_apply_returns_reason_on_invalid_json():
    plan = CanvasEditPlan(wants_edit=True, edit_mode="replace",
                          updated_content_json="not json at all, just prose")
    result, reason = await apply_canvas_edit(plan, "user-1", _email_canvas(), return_reason=True)
    assert result is None and reason == "not_valid_json"


@pytest.mark.asyncio
async def test_apply_refuses_file_backed_office_canvases():
    """A content write to a REAL-file canvas changes nothing the user can
    see (the UI renders the file) — refuse with a reason instead of a
    silent no-op."""
    canvas = {"canvas_id": "c-9", "canvas_type": "office_word",
              "content": {"office_file": "/tmp/x.docx", "file_path": "/tmp/x.docx"}}
    result, reason = await apply_canvas_edit(
        CanvasEditPlan(wants_edit=True, edit_mode="replace",
                       updated_content_json='{"text": "x"}'),
        "user-1", canvas, return_reason=True,
    )
    assert result is None and reason == "file_backed"
    assert "real file" in describe_apply_failure(reason, "office_word", canvas)


# ───────────────────────── legacy canvas healing ─────────────────────────

def test_heal_fills_empty_fields_and_draft_marker_subject():
    healed = normalize_degenerate_content("email", dict(LIVE_INCIDENT_CONTENT))
    assert healed is not None
    assert healed["to"] == "jschulz@blumetric.ca"
    assert healed["subject"] == "Brennan Machinery | Following Up on Your Inquiry"
    assert healed["body"] == LIVE_INCIDENT_CONTENT["body"]  # body never rewritten


def test_heal_never_touches_user_subject_or_nonempty_fields():
    content = {**LIVE_INCIDENT_CONTENT, "subject": "My own hand-typed subject"}
    healed = normalize_degenerate_content("email", content)
    assert healed["subject"] == "My own hand-typed subject"  # marker absent → untouched
    content2 = {**LIVE_INCIDENT_CONTENT, "to": "already@set.io"}
    healed2 = normalize_degenerate_content("email", content2)
    assert healed2 is not None and healed2["to"] == "already@set.io"


def test_heal_noop_for_healthy_or_non_email_canvases():
    assert normalize_degenerate_content("document", "plain text") is None
    healthy = {**LIVE_INCIDENT_CONTENT, "to": "a@b.c", "cc": "d@e.f"}
    assert normalize_degenerate_content("email", healthy) is None


@pytest.mark.asyncio
async def test_try_canvas_edit_heals_degenerate_canvas_before_planning():
    from integrations.chat_orchestrator import ChatOrchestrator

    orch = ChatOrchestrator()
    orch.ai_engines = {}
    orch.llm_service = MagicMock()
    healed_capture = {}

    async def fake_update(user_id, canvas_id, content, canvas_type, title=None, **kw):
        healed_capture["content"] = content
        return {"success": True}

    with patch.object(orch, "_record_chat_step", new=AsyncMock()), \
         patch("tools.canvas_crud_tool.update_canvas_content", new=AsyncMock(side_effect=fake_update)), \
         patch("core.chat_canvas_editor.plan_canvas_edit", new=AsyncMock(
             return_value=CanvasEditPlan(wants_edit=False, reply="hi"))):
        await orch._try_canvas_edit(
            "using past learnings take steps and decide on first contact draft. "
            "include to and cc emails as well",
            [], _email_canvas(), "user-1", "s-1", "exec-1", None,
        )
    assert healed_capture["content"]["to"] == "jschulz@blumetric.ca"


# ───────────────────────── per-app awareness ─────────────────────────

def test_prompt_section_differs_per_app():
    email_sec = app_prompt_section("email", LIVE_INCIDENT_CONTENT)
    sheet_sec = app_prompt_section("sheet", [["a", "b"]])
    office_sec = app_prompt_section("office_word", {"office_file": "/x.docx"})
    code_sec = app_prompt_section("code", "print(1)")

    assert '"to"' in email_sec and "Currently EMPTY fields: to, cc" in email_sec
    assert "A1" in sheet_sec and "To" not in sheet_sec
    assert "REAL file" in office_sec
    assert "plain text" in code_sec
    # alias vocabulary normalizes like the frontend's normalizeCanvasComponent
    assert get_app_spec("sheets").canvas_type == "sheet"
    assert get_app_spec("docs").canvas_type == "document"


@pytest.mark.asyncio
async def test_plan_prompt_carries_the_app_section():
    llm = MagicMock()
    llm._get_handler.return_value.clients = {}
    llm.generate_structured_response = AsyncMock(
        return_value=CanvasEditPlan(wants_edit=True))
    await plan_canvas_edit("fill in to and cc", [], _email_canvas(), llm)
    prompt = llm.generate_structured_response.call_args.kwargs["prompt"]
    assert "CANVAS APP: Email" in prompt
    assert "Currently EMPTY fields: to, cc" in prompt
    assert "SET-FIELD" in prompt


@pytest.mark.asyncio
async def test_plan_raw_json_fallback_rescues_degenerate_replan():
    """Structured replace re-ask returning nothing usable → one RAW
    completion retry parsed locally; a usable payload completes the edit
    plan instead of abandoning the turn."""
    llm = MagicMock()
    llm._get_handler.return_value.clients = {}
    degenerate = CanvasEditPlan(wants_edit=True, edit_mode="replace",
                                updated_content_json=None, reply="")
    llm.generate_structured_response = AsyncMock(return_value=degenerate)
    llm.generate_completion = AsyncMock(return_value={
        "success": True,
        "content": json.dumps({
            "wants_edit": True, "edit_mode": "replace",
            "updated_content_json": json.dumps({"to": "jschulz@blumetric.ca"}),
            "reply": "set To",
        }),
    })
    plan = await plan_canvas_edit(
        "include to and cc emails", [], _email_canvas(), llm,
    )
    assert plan is not None and (plan.updated_content_json or "").strip()
    assert "jschulz@blumetric.ca" in plan.updated_content_json
    assert llm.generate_completion.await_count == 1


# ───────────────────────── failure UX ─────────────────────────

def test_failure_reply_names_empty_fields_with_next_step():
    msg = describe_apply_failure("not_valid_json", "email", _email_canvas())
    assert "TO, CC" in msg and "set to:" in msg and "nothing was changed" in msg


def test_failure_reply_generic_for_ops_mismatch_without_empty_fields():
    full = {**LIVE_INCIDENT_CONTENT, "to": "a@b.c", "cc": "d@e.f"}
    msg = describe_apply_failure("ops_no_longer_match", "email", _email_canvas(full))
    assert "couldn't apply it cleanly" in msg


@pytest.mark.asyncio
async def test_try_canvas_edit_apply_failure_reply_is_actionable():
    from integrations.chat_orchestrator import ChatOrchestrator

    orch = ChatOrchestrator()
    orch.ai_engines = {}
    orch.llm_service = MagicMock()
    with patch.object(orch, "_record_chat_step", new=AsyncMock()), \
         patch.object(orch, "_heal_degenerate_canvas", new=AsyncMock(side_effect=lambda u, c: c)), \
         patch("core.chat_canvas_editor.plan_canvas_edit", new=AsyncMock(
             return_value=CanvasEditPlan(wants_edit=True, edit_mode="replace",
                                         updated_content_json=None, reply=""))), \
         patch("core.chat_canvas_editor.apply_canvas_edit", new=AsyncMock(
             return_value=(None, "not_valid_json"))):
        resp = await orch._try_canvas_edit(
            "fill in to and cc", [], _email_canvas(), "user-1", "s-1", "exec-1", None,
        )
    assert resp is not None and resp["data"]["canvas_edit"]["updated"] is False
    assert resp["data"]["canvas_edit"]["reason"] == "not_valid_json"
    assert "TO, CC" in resp["message"] and "set to:" in resp["message"]
