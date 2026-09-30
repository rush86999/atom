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
    _bounded_email_content,
    _merge_replace_content,
    _requested_product_count,
    _validate_scoped_edit,
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


@pytest.fixture(autouse=True)
def _no_live_fresh_data():
    """Default the co-editor's live-evidence lookup to "not needed" — it runs
    the real tool planner, which fails on the MagicMock llm_service these
    tests install, and the 2026-09-04 fabrication guard then DECLINES the
    whole edit (_try_canvas_edit -> None). Tests that exercise the fresh-data
    path patch fetch_fresh_data_section themselves and win over this."""
    from core.chat_canvas_editor import FreshDataResult

    with patch(
        "core.chat_canvas_editor.fetch_fresh_data_section",
        new=AsyncMock(return_value=FreshDataResult(section="", needed=False, ok=True)),
    ):
        yield

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


class _persisting_store:
    """A canvas store that ACTUALLY persists, so verification can succeed.

    `apply_canvas_edit` reads the canvas back and refuses to report success
    unless the read-back contains what it wrote, bound to an audit id the store
    recorded. A bare `{"success": True}` is not a successful edit any more — it
    is the tool's own claim about its own write — so a test that asserts a
    successful apply has to give the fake the two things a real store gives it:
    what it wrote, and the id of the row it wrote.
    """

    def __init__(self, canvas_id: str, canvas_type: str = "email") -> None:
        self.canvas_id = canvas_id
        self.canvas_type = canvas_type
        self.content: object = None
        self.writes = 0

    def patches(self):
        store = self

        async def _update(user_id, canvas_id, content, canvas_type=None,
                          title=None, **kwargs):
            store.writes += 1
            store.content = content
            return {"success": True, "audit_id": f"audit-{store.writes}",
                    "write_outcome": "committed"}

        async def _read(user_id, canvas_id, **kwargs):
            if store.content is None:
                return {"success": False, "error": "not found"}
            return {"success": True, "canvas_id": store.canvas_id,
                    "canvas_type": store.canvas_type, "content": store.content}

        return (patch("tools.canvas_crud_tool.update_canvas_content",
                      new=AsyncMock(side_effect=_update)),
                patch("tools.canvas_crud_tool.read_canvas",
                      new=AsyncMock(side_effect=_read)))


@pytest.mark.asyncio
async def test_apply_replace_merge_via_crud_layer():
    canvas = _email_canvas()
    store = _persisting_store(str(canvas.get("canvas_id") or "c-1"))
    with store.patches()[0] as upd, store.patches()[1]:
        plan = CanvasEditPlan(
            wants_edit=True, edit_mode="replace",
            updated_content_json=json.dumps({"to": "jschulz@blumetric.ca"}),
            reply="filled To",
        )
        result = await apply_canvas_edit(plan, "user-1", canvas)
    assert result and result["success"]
    assert result["postcondition_verified"] is True
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


# ─────────────── office-file canvases carry legacy generic types ───────────────
# Live incident 2026-09-10 (canvas 7f078cea…): the office .xlsx canvas stored
# the registry canvas_type "sheets" (OFFICE_COMPONENT_MAP for .xlsx) with
# content {"office_file": …}. get_app_spec() maps "sheets" onto the generic
# GRID app (the frontend alias vocabulary), so the co-editor planned a cell
# edit against an office BINDING, reproduced the content byte-for-byte and
# answered "I read the canvas and it already reflects that" — a false claim:
# the file still had its USD and Exch columns. The file binding must win.

OFFICE_CANVAS_CONTENT = {
    "office_file": "data/office/chat-Draft-I-searched-Workdrive-live-for-Trum-2fb2bc2e.xlsx",
    "file_path": "data/office/chat-Draft-I-searched-Workdrive-live-for-Trum-2fb2bc2e.xlsx",
    "format": "xlsx",
}


def _office_canvas(canvas_type="sheets", content=None):
    return {
        "canvas_id": "7f078cea-5d6e-487b-b7b9-145336edf42c",
        "canvas_type": canvas_type,
        "title": 'Draft — I searched Workdrive live for "Trumatic-L3030S"',
        "content": dict(content if content is not None else OFFICE_CANVAS_CONTENT),
    }


@pytest.mark.asyncio
async def test_apply_refuses_legacy_typed_office_canvas_as_file_backed():
    result, reason = await apply_canvas_edit(
        CanvasEditPlan(wants_edit=True, edit_mode="replace",
                       updated_content_json=json.dumps(OFFICE_CANVAS_CONTENT)),
        "user-1", _office_canvas(), return_reason=True,
    )
    assert result is None and reason == "file_backed"
    assert "real file" in describe_apply_failure(reason, "sheets", _office_canvas())


def test_prompt_section_detects_office_content_despite_legacy_type():
    sec = app_prompt_section("sheets", OFFICE_CANVAS_CONTENT)
    assert "REAL file" in sec
    assert "grid of rows" not in sec


def test_resolve_app_spec_prefers_office_format_over_alias():
    from core.canvas_app_schema import resolve_app_spec

    assert resolve_app_spec("sheets", OFFICE_CANVAS_CONTENT).canvas_type == "office_excel"
    assert resolve_app_spec("docs", {"office_file": "/tmp/a.docx"}).canvas_type == "office_word"
    assert resolve_app_spec(
        "presentation", {"office_file": "/tmp/a.pptx", "format": "pptx"}
    ).canvas_type == "office_pptx"
    # Plain grid/text canvases are untouched by the office override.
    assert resolve_app_spec("sheets", [["a", "b"]]).canvas_type == "sheet"
    assert resolve_app_spec("docs", "hello").canvas_type == "document"


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


def test_requested_scope_count_reconciles_named_non_slitter_and_alternatives():
    assert _requested_product_count([
        "reconcile four non-slitter machines including No. 622, plus "
        "SLE24-16 and three alternative slitters"
    ]) == 8
    assert _requested_product_count([
        "four requested machines followed by three alternatives"
    ]) == 7


def test_scoped_update_rejects_placeholders_but_allows_payment_terms_tbd():
    body = (
        "<p>Requested equipment and alternatives</p>"
        "<table><tr><th>#</th><th>Description</th><th>Price</th><th>Delivery</th></tr>"
        "<tr><td>1</td><td>Roper Whitney No. 381</td><td>$2,902.00</td><td>10-11 weeks</td></tr>"
        "<tr><td>2</td><td>Linmac U-22</td><td>$1,777.00</td><td>3-4 months</td></tr>"
        "<tr><td>3</td><td>Manual Flanger</td><td>$1,609.00</td><td>3-4 weeks</td></tr>"
        "<tr><td>4</td><td>Tennsmith SLE24-16</td><td>$8,880.00</td><td>11-12 weeks</td></tr>"
        "<tr><td>5</td><td>TK 1624</td><td>$8,040.00</td><td>4-6 weeks</td></tr>"
        "<tr><td>6</td><td>Tin Knocker Gang Slitter</td><td>$12,838.00</td><td>In Stock</td></tr>"
        "<tr><td>7</td><td>GSL48-16</td><td>$14,166.00</td><td>6-8 weeks</td></tr>"
        "<tr><td>8</td><td>Roper Whitney No. 622</td><td>$2,421.00</td><td>In Stock</td></tr>"
        "</table><p>Regards, Rish M.</p><p>Payment Terms: TBD</p>"
    )
    request = (
        "apply all eight machines with actual prices, distinguish alternatives, "
        "keep the footer, and use no square brackets"
    )
    assert _validate_scoped_edit({"body": "<table></table>"}, {"body": body}, [request]) is None
    bad = body.replace("$8,880.00", "TBD").replace(
        "TK 1624", "[Slitter alternative — from email]"
    )
    reason = _validate_scoped_edit({"body": "<table></table>"}, {"body": bad}, [request])
    assert reason and reason.startswith("scope_placeholder")


def test_bounded_email_merge_keeps_footer_and_links():
    old = (
        "<p>Hi Steve,</p><table><tr><td>old</td></tr></table>"
        "<p>Regards, Rish M.</p><a href=\"https://brennan.ca/\">Brennan</a>"
    )
    new = (
        "<p>Hi Steve,</p><table><tr><td>new</td></tr><tr><td>alt</td></tr></table>"
        "<p>Alternative option</p><p>Regards, Someone Else</p>"
        "<a href=\"https://brennan.ca/\">Brennan</a>"
    )
    merged = _bounded_email_content({"body": old}, {"body": new})
    assert merged is not None
    assert "new" in merged["body"] and "alt" in merged["body"]
    assert "Regards, Rish M." in merged["body"]
    assert "Someone Else" not in merged["body"]
    assert "https://brennan.ca/" in merged["body"]


# ---------------------------------------------------------------------------
# Scope validation sources (2026-09-29 live incident): validate the DIFF
# against the artifact's own previous state — never against conversation
# history. A pasted data row (381<TAB>167072381…) in history made every
# edit plan fail scope_missing_product because no email body contains a
# raw catalog number, so the user's explicit price update dead-ended
# after 3 honest retries.
# ---------------------------------------------------------------------------

EMAIL_BODY_8 = (
    "<p>Requested equipment</p>"
    "<table><tr><th>#</th><th>Description</th><th>Price</th></tr>"
    "<tr><td>1</td><td>Roper Whitney No. 381</td><td>$2,902.00</td></tr>"
    "<tr><td>2</td><td>Linmac U-22</td><td>$1,777.00</td></tr>"
    "<tr><td>3</td><td>Tennsmith SLE24-16</td><td>$8,880.00</td></tr>"
    "</table><p>Regards, Rish M.</p>"
)


def test_pasted_lookup_data_in_history_never_poisons_edit_scope():
    """The user's update instruction names 381; the pasted data row lives
    only in HISTORY. The edited email keeps every product it had and
    changes one price — the scope check must pass."""
    from core.chat_canvas_editor import _scope_user_messages  # noqa: F401
    from core.chat_canvas_editor import _validate_scoped_edit

    instruction = ("as you found the latest price for the roper 381 roll "
                   "bender, update the email price accordingly")
    new_body = EMAIL_BODY_8.replace("$2,902.00", "$3,254.00")
    assert _validate_scoped_edit(
        {"body": EMAIL_BODY_8}, {"body": new_body}, [instruction]) is None


def test_edit_may_not_silently_drop_a_product_identity():
    """Preservation invariant: a regeneration that drops a product code
    the canvas already had (without the instruction naming it) is content
    loss — refused even though no request code is missing."""
    from core.chat_canvas_editor import _validate_scoped_edit

    instruction = "update the email price accordingly for the 381"
    new_body = EMAIL_BODY_8.replace(
        "<tr><td>2</td><td>Linmac U-22</td><td>$1,777.00</td></tr>", ""
    ).replace("$2,902.00", "$3,254.00")
    reason = _validate_scoped_edit(
        {"body": EMAIL_BODY_8}, {"body": new_body}, [instruction])
    assert reason and reason.startswith("scope_dropped_product"), reason


def test_named_identity_may_leave_the_canvas():
    """'Remove U-22 from the email' names the identity it removes — the
    preservation check exempts codes the instruction itself names."""
    from core.chat_canvas_editor import _validate_scoped_edit

    instruction = "remove the U-22 line from the email"
    new_body = EMAIL_BODY_8.replace(
        "<tr><td>2</td><td>Linmac U-22</td><td>$1,777.00</td></tr>", "")
    assert _validate_scoped_edit(
        {"body": EMAIL_BODY_8}, {"body": new_body}, [instruction]) is None


# ---------------------------------------------------------------------------
# FALSE-SUCCESS NARRATION GATE (2026-09-29 live): the edit lane declined
# (planner unavailable), and the reply leg narrated an "updated quote" as
# text — no canvas write, no audit row, yet the user read success. If the
# turn had an open canvas, was edit-shaped, and no audit row carries THIS
# turn's operation id, a success claim must be replaced with the honest
# outcome. The four correct wordings:
#   unavailable provider -> honest "did not apply"
#   legitimate decline   -> honest decline (existing no-apply branch)
#   pending background   -> "still running" (existing fork branch)
#   successful edit      -> claim allowed (audit receipt exists)
# ---------------------------------------------------------------------------

def test_reply_claiming_canvas_update_without_receipt_is_detected():
    from core.chat_canvas_editor import reply_claims_canvas_change

    assert reply_claims_canvas_change(
        "Please find our updated quote below for the requested equipment:")
    assert reply_claims_canvas_change(
        "I've updated the email with the new price.")
    assert reply_claims_canvas_change(
        "Done — applied the change to the draft.")
    # denials / pending / questions are NOT success claims
    assert not reply_claims_canvas_change(
        "I didn't apply that canvas change, so nothing was changed.")
    assert not reply_claims_canvas_change(
        "The canvas edit is still running in the background.")
    assert not reply_claims_canvas_change(
        "Which line should I update?")


def test_receipt_check_queries_audit_by_operation_id(tmp_path):
    from core.chat_canvas_editor import canvas_operation_has_receipt

    # No DB row -> no receipt (the function must not raise).
    assert canvas_operation_has_receipt(
        "u1", "00000000-0000-0000-0000-000000000000", "exec-x") is False


def test_fallback_after_failed_pin_excludes_that_route():
    """Fork 91fedfd1 (2026-09-29): the pinned plan route truncated at
    max_tokens, and the unpinned fallback re-ranked the SAME route —
    repeating a deterministic failure until the plan budget died. The
    fallback must exclude the failed pin so the cascade lands on a
    different model."""
    import asyncio

    from core.llm.pinned_planning import pinned_structured_call

    seen_kwargs = []

    class _FakeLLM:
        async def generate_structured_response(self, **kwargs):
            seen_kwargs.append(kwargs)
            if kwargs.get("provider_model") == ("deepseek", "deepseek-v4-pro"):
                return None  # the pin's route failed (e.g. truncation)
            return "ok"

    result = asyncio.run(pinned_structured_call(
        _FakeLLM(),
        prompt="plan the edit",
        response_model=dict,
        system_instruction="json",
        call_kwargs={"provider_model": ("deepseek", "deepseek-v4-pro")},
        log_label="canvas edit planning",
        task_type="planning",
    ))
    assert result == "ok"
    assert len(seen_kwargs) == 2, "pin attempt + one fallback"
    assert seen_kwargs[0].get("provider_model") == (
        "deepseek", "deepseek-v4-pro")
    assert seen_kwargs[1].get("exclude_provider_model") == (
        "deepseek", "deepseek-v4-pro"), (
        "the fallback must carry the failed route as an exclusion")
    assert seen_kwargs[1].get("provider_model") is None


def test_failed_pin_exclusion_filter():
    """The cascade's options filter: the failed route is dropped from a
    multi-route pool, and a single-option pool is left intact (an empty
    dispatch pool is worse than a known route)."""
    from core.llm.byok_handler import apply_failed_pin_exclusion

    pool = [("deepseek", "deepseek-v4-pro"), ("deepseek", "deepseek-flash"),
            ("opencode-go", "kimi-k2.7-code")]
    out = apply_failed_pin_exclusion(pool, ("deepseek", "deepseek-v4-pro"))
    assert ("deepseek", "deepseek-v4-pro") not in out
    assert len(out) == 2
    # single-option pool untouched
    assert apply_failed_pin_exclusion(
        [("deepseek", "deepseek-v4-pro")],
        ("deepseek", "deepseek-v4-pro")) == [("deepseek", "deepseek-v4-pro")]
    # no exclusion -> unchanged
    assert apply_failed_pin_exclusion(pool, None) == pool


def test_observed_false_success_sentence_is_caught_by_the_receipt_gate():
    """The exact narration that reached the user on 2026-09-29 (the edit
    lane declined, the reply narrated an updated quote) must be detected
    by the generic claim detector — no business vocabulary required."""
    from core.chat_canvas_editor import reply_claims_canvas_change

    assert reply_claims_canvas_change(
        "Hi Steve,\n\nThank you for your inquiry. Please find our updated "
        "quote below for the requested equipment:")


def test_ambiguous_render_names_sheets_holding_surplus_candidates():
    """Live 2026-09-29: No. 381 matched 10 rows; the renderer showed the
    first three (all RoperWhitney) and the user read the list as
    exhaustive — 'the search didn't reveal the Tennsmith sheet results'.
    When candidates exceed the display cap, the surplus count and the
    sheets holding them must be stated (generic; no business terms)."""
    from core.answer_presentation import _render_target

    def cand(ref):
        return {"ref": ref, "identity": {"status": "bound",
                                         "references": []},
                "values": [{"col": "E", "basis": "PRICE", "display": "1"}]}
    target = {
        "item": "No. 381", "aliases": [],
        "identity": {"status": "multiple",
                     "candidates": [cand(f"RoperWhitney!R88"),
                                    cand("RoperWhitney!R89"),
                                    cand("RoperWhitney!R90"),
                                    cand("Tennsmith!R338")]},
        "field": {"status": "present",
                  "values": [{"col": "E", "basis": "PRICE",
                              "display": "1"}]},
    }
    line = _render_target(target, "No. 381")
    assert "Tennsmith" in line, line
    assert "+1 more match" in line, line
    # cap not exceeded -> no surplus note
    target["identity"]["candidates"] = target["identity"][
        "candidates"][:2]
    line2 = _render_target(target, "No. 381")
    assert "more match" not in line2


def test_workbook_result_card_payload_shapes():
    """The chat UI card payload: found / ambiguous / absent items,
    provenance (ref + identity cells + other bases), source + coverage
    footer. Generic structural fields only."""
    from core.answer_presentation import workbook_result_card

    sr = {
        "source_identity": {
            "file_name": "recipe log.xlsx", "live_vs_saved": "saved copy",
            "ingested_at": "2026-09-07T23:06:19"},
        "coverage": {"indexed_sheets": 46, "scanned_sheets": 46},
        "targets": [
            {"item": "Sourdough loaf", "identity": {
                "status": "multiple",
                "candidates": [
                    {"ref": "Breads!R14",
                     "identity": {"status": "bound", "references": [
                         {"cell": "A14", "row": 14}]},
                     "values": [{"basis": "HYDRATION", "display": "78%"},
                                {"basis": "FLOUR", "display": "450g"}]},
                    {"ref": "Breads!R3",
                     "identity": {"status": "bound", "references": [
                         {"cell": "A3", "row": 3}]},
                     "values": [{"basis": "HYDRATION", "display": "70%"}]},
                ]}},
            {"item": "rye", "identity": {
                "status": "bound",
                "candidates": [
                    {"ref": "Breads!R3",
                     "identity": {"status": "bound", "references": [
                         {"cell": "A3", "row": 3}]},
                     "values": [{"basis": "HYDRATION", "display": "70%"},
                                {"basis": "FLOUR", "display": "400g"}]}]}},
            {"item": "milk bread", "identity": {"status": "none",
                                                "candidates": []}},
        ],
    }
    card = workbook_result_card(sr)
    assert card["schema"] == "workbook-result-1"
    assert card["file"] == "recipe log.xlsx"
    assert "saved copy" in (card["source_note"] or "")
    assert "46 sheets" in (card["coverage"] or "")
    amb, found, absent = card["items"]
    assert amb["status"] == "ambiguous"
    assert amb["candidates"][0]["ref"] == "Breads!R14"
    assert found["status"] == "found" and found["value"] == "70%"
    assert found["ref"] == "Breads!R3" and found["identity_cells"] == ["A3"]
    assert found["other_bases"] == [{"basis": "FLOUR", "display": "400g"}]
    assert absent["status"] == "absent" and "value" not in absent
    # absent artifacts -> no card (nothing to present)
    assert workbook_result_card({"source_identity": {}}) is None
