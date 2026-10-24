"""Local replays/controls for the attempt-4 product failures.

These tests do not launch a campaign. They replay the preserved attempt-4
L3 answer and S3 canvas/grounding case through the repaired boundaries,
plus changed-subject/code, multiple-subject, explicit-both, unsupported,
and zero-write controls.
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from core.answer_boundary import EXPLICIT_LIMITATION, present_answer
from core.chat_tool_planner import (
    figure_issues,
    serialize_canvas_evidence,
)

ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = (ROOT / "backend/scripts/orchestration_acceptance/journey_matrix/"
            "l1_l2_l3_integrated_served_20261020")
ATTEMPT4 = EVIDENCE / "attempt4_result.json"
ATTEMPT5 = EVIDENCE / "attempt5_result.json"
ATTEMPT6 = EVIDENCE / "attempt6_result.json"
ATTEMPT8 = (ROOT / "docs/acceptance/release_evidence_20261023/"
            "live_world_rehearsal_attempt8/live_rehearsal_result.json")
CAPTURED = json.loads(ATTEMPT4.read_text())
CAPTURED5 = json.loads(ATTEMPT5.read_text())
CAPTURED6 = json.loads(ATTEMPT6.read_text())
CAPTURED8 = json.loads(ATTEMPT8.read_text())
L3 = CAPTURED["steps"]["l3"]
S3 = CAPTURED["steps"]["s3"]
L3_ASK = L3["ask"]
S3_ASK = S3["ask"]
CANVAS = S3["canvas_before"]


def _l3_envelope_and_answer() -> tuple[str, str]:
    served = L3["initial_response"]["message"]
    envelope, answer = served.split("\n\n", 1)
    return envelope, answer


def _load_runner():
    path = EVIDENCE / "run_composed_served_attempt5.py"
    spec = importlib.util.spec_from_file_location(
        "attempt5_repair_runner", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _fact(subject, field, value, source="records.txt") -> dict:
    return {"subject": subject, "field": field,
            "value": value, "source": source}


def _tool_block(*records: tuple[str, str]) -> str:
    return (
        "LIVE TOOL RESULTS (documents.search) — hybrid search over the "
        "workspace's ingested documents:\n"
        + "\n".join(
            f"- [ingested] {name}: {body}" for name, body in records))


# ---------------------------------------------------------------------------
# L3 boundary capture + repair
# ---------------------------------------------------------------------------
def test_captured_l3_boundaries_are_the_same_echo():
    """served == persisted == reloaded: the finalization/persistence stages
    passed the reply-generation echo through unchanged. The first boundary
    that introduced the internal block is therefore the model output (or
    the prompt/evidence handoff that invited the echo), not persistence."""
    envelope, answer = _l3_envelope_and_answer()
    persisted = [
        row for row in (L3.get("persisted_rows") or [])
        if row.get("role") == "assistant"]
    reloaded = (L3.get("fresh_history") or {}).get(
        "assistant_response") or {}
    assert envelope.startswith("LIVE TOOL RESULTS (documents.search)")
    assert "BASALT-13" in envelope
    assert "QUARTZ-77" in answer
    assert L3["initial_response"]["message"] == persisted[-1]["content"]
    assert L3["initial_response"]["message"] == reloaded["message"]


def test_captured_l3_envelope_is_stripped_and_fact_survives():
    envelope, answer = _l3_envelope_and_answer()
    clean = present_answer(
        L3["initial_response"]["message"], envelope, L3_ASK)
    assert clean == answer
    assert "LIVE TOOL RESULTS" not in clean
    assert "QUARTZ-77" in clean
    assert "BASALT-13" not in clean
    assert "l3_zephyr9_fixture.txt" in clean


def test_captured_attempt5_grep_envelope_is_stripped():
    """Attempt 5 emitted the em-dash grep header; the boundary must remove
    that carrier shape too, not only the parenthesis header."""
    served = CAPTURED5["steps"]["l3"]["initial_response"]["message"]
    assert served.startswith("LIVE TOOL RESULTS — regex scan")
    clean = present_answer(served, None, L3_ASK)
    assert "LIVE TOOL RESULTS" not in clean
    assert "QUARTZ-77" in clean
    assert "BASALT-13" not in clean


def test_comparison_scope_contract_keeps_the_broad_instruction():
    from core.workbook_read_artifact import accepted_comparison_scope

    accepted = {
        "requested_fields": ["Valid Until date"],
        "constraints": [],
    }
    assert accepted_comparison_scope(accepted, S3_ASK) is True
    follow = (
        "What is the current Valid until date on the draft, and does it "
        "still match the approved record?")
    assert accepted_comparison_scope(
        {"requested_fields": ["Valid until date", "match status"],
         "constraints": []}, follow) is False
    assert accepted_comparison_scope(
        {"requested_fields": ["Valid Until date"],
         "constraints": ["Only compare the date."]}, S3_ASK) is False


def test_missing_comparison_limitation_is_draft_grounded():
    from core.workbook_read_artifact import comparison_missing_limitation

    req = CAPTURED5["steps"]["s3"]["requirement_summary"]
    text = comparison_missing_limitation(
        canvas={"content": CANVAS, "canvas_id": "c",
                "title": "Quotation"},
        requirement=dict(req, broader_comparison=True),
        source_label="approved_records_q2026_114.txt")
    assert "2026-12-31" in text
    assert "2027-03-31" not in text
    assert "comparison itself was not recorded" in text
    assert "Broader comparison obligation: OPEN" in text
    assert "approved_records_q2026_114.txt" in text


def test_captured_attempt6_full_text_excerpt_is_stripped():
    """Attempt 6 emitted the line-numbered VFS full text (including the
    decoy) as prose. That block is an internal evidence carrier; the
    boundary must remove it and leave the supported answer."""
    served = CAPTURED6["steps"]["l3"]["initial_response"]["message"]
    assert "L1:" in served and "BASALT-13" in served
    clean = present_answer(served, None, L3_ASK)
    assert "L1:" not in clean
    assert "BASALT-13" not in clean
    assert "QUARTZ-77" in clean
    assert _load_runner().l3_answer_contract(clean) is True


def test_single_line_numbered_citation_is_not_removed():
    text = "The launch code is QUARTZ-77 (L3: fixture line)."
    assert present_answer(text, None, L3_ASK) == text


def test_wrong_subject_fallback_is_a_limitation():
    """Reproduced on 824a94c5b: an empty answer plus Zephyr-9/Halcyon-2
    sentences returned the Halcyon sentence as if it answered Zephyr-9.
    The fallback may only use a unique structured association."""
    tool = _tool_block(
        ("records.txt",
         "Zephyr-9: QUARTZ-77.\n"
         "The launch code for project Halcyon-2 is BASALT-13."))
    out = present_answer(
        "", tool, "What is the launch code for Zephyr-9?")
    assert out == EXPLICIT_LIMITATION
    assert "Halcyon" not in out
    assert "BASALT-13" not in out
    assert "QUARTZ-77" not in out


def test_captured_envelope_only_answer_returns_a_limitation():
    envelope, _answer = _l3_envelope_and_answer()
    out = present_answer(envelope, envelope, L3_ASK)
    assert out == EXPLICIT_LIMITATION
    assert "LIVE TOOL RESULTS" not in out
    assert "BASALT-13" not in out


def test_prose_with_both_codes_is_not_certified_by_the_boundary():
    """The boundary preserves substantive prose; it must not use anchor
    presence to certify it. The real L3 contract still rejects the decoy."""
    tool = _tool_block(
        ("records.txt",
         "The launch code for project Zephyr-9 is QUARTZ-77.\n"
         "The launch code for project Halcyon-2 is BASALT-13."))
    prose = (
        "The launch code for Zephyr-9 is QUARTZ-77. "
        "The launch code for project Halcyon-2 is BASALT-13.")
    out = present_answer(prose, tool, L3_ASK)
    assert out == prose, "the boundary must not rewrite/certify prose"
    assert _load_runner().l3_answer_contract(out) is False


def test_structured_fallback_uses_changed_identifiers():
    fact = _fact("Zephyr-10", "launch code", "QUARTZ-88", "fixture_b.txt")
    out = present_answer(
        "", "", "what is the launch code for Zephyr-10?",
        supported_facts=[fact])
    assert out == (
        "Zephyr-10 launch code: QUARTZ-88 (Source: fixture_b.txt)")
    assert "QUARTZ-77" not in out


def test_two_requested_subjects_need_two_explicit_associations():
    facts = [
        _fact("Zephyr-9", "launch code", "QUARTZ-77"),
        _fact("Halcyon-2", "archive key", "BASALT-13"),
    ]
    assert present_answer(
        "", "", "tell me both codes", supported_facts=facts) == (
        EXPLICIT_LIMITATION)
    assert present_answer(
        "", "", "tell me Zephyr-9's code",
        supported_facts=[facts[0]]) == (
        "Zephyr-9 launch code: QUARTZ-77 (Source: records.txt)")


def test_incomplete_or_duplicate_structured_facts_are_limitations():
    assert present_answer(
        "", "", "code", supported_facts=[
            {"subject": "Zephyr-9", "value": "QUARTZ-77"}]) == (
        EXPLICIT_LIMITATION)
    same = _fact("Zephyr-9", "launch code", "QUARTZ-77")
    assert present_answer(
        "", "", "code", supported_facts=[same, dict(same)]) == (
        EXPLICIT_LIMITATION)


@pytest.mark.asyncio
async def test_orchestrator_final_return_strips_the_envelope():
    import integrations.chat_orchestrator as co

    envelope, answer = _l3_envelope_and_answer()
    orch = co.ChatOrchestrator()
    orch.ai_engines = {}
    llm = MagicMock()
    llm.generate_completion = AsyncMock(return_value={
        "success": True,
        "content": envelope + "\n\n" + answer,
        "model": "llama3.1:8b",
        "provider": "ollama",
    })
    orch.llm_service = llm
    out = await orch._get_qwen_response(L3_ASK, [])
    assert out is not None
    assert "LIVE TOOL RESULTS" not in out["content"]
    assert "QUARTZ-77" in out["content"]


@pytest.mark.asyncio
async def test_orchestrator_envelope_only_returns_the_limitation():
    import integrations.chat_orchestrator as co

    envelope, _answer = _l3_envelope_and_answer()
    orch = co.ChatOrchestrator()
    orch.ai_engines = {}
    llm = MagicMock()
    llm.generate_completion = AsyncMock(return_value={
        "success": True,
        "content": envelope,
        "model": "llama3.1:8b",
        "provider": "ollama",
    })
    orch.llm_service = llm
    out = await orch._get_qwen_response(L3_ASK, [])
    assert out is not None
    assert out["content"] == EXPLICIT_LIMITATION
    assert "BASALT-13" not in out["content"]


def test_l3_ordinary_quotation_is_not_stripped():
    text = (
        'The draft says "Net 45", and the approved record says "Net 30". '
        "The launch code for project Zephyr-9 is QUARTZ-77 from "
        "l3_zephyr9_fixture.txt.")
    tool = _tool_block(
        ("l3_zephyr9_fixture.txt",
         "The launch code for project Zephyr-9 is QUARTZ-77."))
    clean = present_answer(text, tool, L3_ASK)
    assert 'The draft says "Net 45"' in clean
    assert "QUARTZ-77" in clean


def test_orchestrator_wires_the_repairs_at_the_boundaries():
    from integrations import chat_orchestrator as co

    src = Path(co.__file__).read_text()
    assert "from core.answer_boundary import present_answer" in src
    assert "present_answer(_content, _tool_block, message)" in src
    assert "serialize_canvas_evidence(" in src
    assert "_canvas_ctx, canvas_context" in src
    assert "figure_issues(" in src


# ---------------------------------------------------------------------------
# S3 figure grounding replay
# ---------------------------------------------------------------------------
S3_DRAFT_REPLY = (
    "The draft quotation lists a unit price of $48,000.00. "
    "The Valid Until date is 2026-12-31 in the draft and the approved "
    "record.")
S3_SOURCE_REPLY = (
    "The approved record lists a unit price of $48,000.00.")
S3_UNSUPPORTED_REPLY = "The unit price is $99,000.00."
S3_TOOL = (
    "LIVE TOOL RESULTS (documents.search):\n"
    "- [ingested] approved_records_q2026_114.txt: Approved valid until: "
    "2026-12-31")


def test_captured_s3_canvas_supports_the_challenged_figure():
    evidence = serialize_canvas_evidence(
        None, {"content": CANVAS})
    assert "$48,000.00" in evidence
    assert figure_issues(
        S3_DRAFT_REPLY,
        canvas_text=evidence,
        tool_text=S3_TOOL,
        message=S3_ASK,
    ) == []


def test_s3_without_passed_canvas_reproduces_the_false_positive():
    """The old guard read only the local (empty) canvas. Replaying that
    state flags the draft-supported figure; this is the repair target."""
    assert figure_issues(
        S3_DRAFT_REPLY,
        canvas_text="",
        tool_text=S3_TOOL,
        message=S3_ASK,
    )[0]["kind"] == "unsupported"


def test_s3_source_attribution_still_matters():
    misattributed = figure_issues(
        S3_SOURCE_REPLY,
        canvas_text=CANVAS,
        tool_text=S3_TOOL,
        message=S3_ASK,
    )
    assert misattributed[0]["kind"] == "misattributed_to_source"
    supported_tool = (
        S3_TOOL + "\n- [ingested] approved_records_q2026_114.txt: "
        "Approved unit price: $48,000.00")
    assert figure_issues(
        S3_SOURCE_REPLY,
        canvas_text=CANVAS,
        tool_text=supported_tool,
        message=S3_ASK,
    ) == []


def test_s3_unsupported_figure_is_still_withheld():
    issues = figure_issues(
        S3_UNSUPPORTED_REPLY,
        canvas_text=CANVAS,
        tool_text=S3_TOOL,
        message=S3_ASK,
    )
    assert issues[0]["kind"] == "unsupported"
    assert issues[0]["figure"] == "$99,000.00"


def test_s3_number_normalization_preserves_the_value():
    assert figure_issues(
        "The draft price is $48,000.",
        canvas_text=CANVAS,
        tool_text=S3_TOOL,
        message=S3_ASK,
    ) == []


def test_s3_turn_budget_remains_95_seconds():
    from integrations import chat_orchestrator as co

    assert co.CHAT_TURN_BUDGET_DEFAULT_SECONDS == 95.0


def test_serialize_canvas_evidence_prefers_the_available_context():
    assert "$48,000.00" in serialize_canvas_evidence(
        None, {"content": CANVAS})
    assert "$48,000.00" in serialize_canvas_evidence(
        {"content": CANVAS}, None)
    assert "$48,000.00" in serialize_canvas_evidence(
        {"canvas_content": CANVAS}, None)
    assert serialize_canvas_evidence(None, None) == ""


def test_canvas_local_empty_does_not_shadow_resolved_context():
    local = {"content": ""}
    resolved = {"content": CANVAS}
    evidence = serialize_canvas_evidence(local, resolved)
    assert "$48,000.00" in evidence


def test_canvas_conflicting_identities_are_not_silently_chosen():
    assert serialize_canvas_evidence(
        {"canvas_id": "a", "content": CANVAS},
        {"canvas_id": "b", "content": CANVAS}) == ""
    assert serialize_canvas_evidence(
        {"canvas_id": "a", "revision": 1, "content": CANVAS},
        {"canvas_id": "a", "revision": 2, "content": CANVAS}) == ""


@pytest.mark.asyncio
async def test_orchestrator_replaces_unsupported_comparison_claim(monkeypatch):
    import integrations.chat_orchestrator as co
    from core.workbook_read_artifact import comparison_missing_limitation

    fabricated = (
        "Based on your uploaded Approved Records document, the Valid Until "
        "date in the draft is 2026-12-31, while the approved record "
        "indicates 2027-03-31. This suggests a difference.")
    orch = co.ChatOrchestrator()
    orch.ai_engines = {}
    llm = MagicMock()
    llm.generate_completion = AsyncMock(return_value={
        "success": True, "content": fabricated,
        "model": "llama3.1:8b", "provider": "ollama"})
    orch.llm_service = llm
    req = dict(CAPTURED5["steps"]["s3"]["requirement_summary"],
               broader_comparison=True)
    session = {
        "id": "s-cmp",
        "history": [],
        "_evidence_requirement_exec-cmp": req,
    }
    monkeypatch.setattr(
        co, "_context_backed_fulfillment",
        lambda *a, **k: {"state": "partial", "missing_comparison": True,
                         "supplied_fields": ["expiration_date"]})
    out = await orch._get_qwen_response(
        S3_ASK, [], execution_id="exec-cmp", workspace_id="ws-cmp",
        session=session, canvas_context={
            "canvas_id": "c", "title": "Quotation",
            "content": CANVAS})
    assert out is not None
    assert "2027-03-31" not in out["content"]
    assert "2026-12-31" in out["content"]
    assert "comparison itself was not recorded" in out["content"]
    assert "Broader comparison obligation: OPEN" in out["content"]


# ---------------------------------------------------------------------------
# Zero-write controls preserved from attempt 4
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("check", [
    "comparison_zero_writes",
    "comparison_draft_unchanged",
    "continuation_zero_writes",
    "continuation_draft_unchanged",
    "restart_zero_new_writes",
    "restart_canvas_unchanged",
])
def test_attempt4_zero_write_controls(check):
    assert CAPTURED["checks"][check] is True


def test_attempt4_remains_non_passing():
    assert CAPTURED["pass"] is False
    assert CAPTURED["first_failure"] == "l3_untruthful_answer"
    assert CAPTURED["checks"]["comparison_truthful_date"] is False


def test_attempt5_shape_carrier_prefix_is_removed_body_retained():
    """Replay of the attempt-5 carrier shape. The paragraph body is the
    fixture text; the tool block below mirrors what the planner supplies."""
    text = (
        "1. [ingested] l3_zephyr9_fixture.txt: ATOM PHASE D FIXTURE — "
        "internal notes.\nProject Zephyr-9 launch planning.\nThe launch "
        "code for project Zephyr-9 is QUARTZ-77.\nOwner: R. Parikh. "
        "Team: acceptance.\n\nThe launch code for project Zephyr-9 was "
        "found in the document \"l3_zephyr9_fixture.txt\" as QUARTZ-77.")
    tool = _tool_block(
        ("l3_zephyr9_fixture.txt",
         "ATOM PHASE D FIXTURE — internal notes. "
         "Project Zephyr-9 launch planning. "
         "The launch code for project Zephyr-9 is QUARTZ-77. "
         "Owner: R. Parikh. Team: acceptance."))
    clean = present_answer(text, tool, L3_ASK)
    assert "[ingested]" not in clean
    assert "ATOM PHASE D FIXTURE" in clean
    assert "Owner: R. Parikh" in clean
    assert "QUARTZ-77" in clean
    assert "l3_zephyr9_fixture.txt" in clean


def test_attempt7_shape_carrier_prefix_is_removed_body_retained():
    """Replay of the inline carrier shape; the attempt-7 result itself used
    a different VFS excerpt, so this is a shape control, not a capture."""
    text = (
        "Based on the live tool results from your uploaded documents, I "
        "found one matching document: [ingested] l3_zephyr9_fixture.txt: "
        "ATOM PHASE D FIXTURE — internal notes. Project Zephyr-9 launch "
        "planning.\n\nFrom this document, the launch code for project "
        "Zephyr-9 is QUARTZ-77. \n\nSource: [ingested] "
        "l3_zephyr9_fixture.txt")
    tool = _tool_block(
        ("l3_zephyr9_fixture.txt",
         "ATOM PHASE D FIXTURE — internal notes. "
         "Project Zephyr-9 launch planning."))
    clean = present_answer(text, tool, L3_ASK)
    assert "I found one matching document: [ingested]" not in clean
    assert clean.startswith("l3_zephyr9_fixture.txt: ATOM PHASE D FIXTURE")
    assert "ATOM PHASE D FIXTURE" in clean
    assert "Project Zephyr-9 launch planning" in clean
    assert "QUARTZ-77" in clean
    assert "l3_zephyr9_fixture.txt" in clean


def test_ordinary_quotation_with_ingested_marker_is_preserved():
    """The exact reported reproduction: a user-facing quotation must not be
    mistaken for an evidence carrier merely because it contains the marker."""
    text = (
        'You wrote: "[ingested] is the tag the importer adds."\n\n'
        "In this workspace that tag is metadata, not part of the document "
        "body.")
    tool = _tool_block(("l3_zephyr9_fixture.txt", "QUARTZ-77"))
    message = "What does that tag mean in this workspace?"
    assert present_answer(text, tool, message) == text
    assert present_answer(text, None, message) == text


@pytest.mark.parametrize("text", [
    "The tag [ingested] means imported.\n\nSecond paragraph.",
    "Here is my note: [ingested] is just a label.\n\n"
    "It is not the document body.",
    "Please keep this quote: [ingested] appears in the first line.\n\n"
    "And the next paragraph.",
    "1. [ingested] is a marker, not a source.\n\nSecond paragraph.",
    "Based on the live tool results, the tag [ingested] is metadata.\n\n"
    "It is not the document body.",
])
def test_ingested_marker_mentions_are_preserved(text):
    assert present_answer(text, None, "explain the tag") == text


def test_carrier_shape_without_matching_evidence_is_preserved():
    """A carrier-shaped paragraph is only internal when its named source is
    actually in the tool block. Otherwise it is ordinary user-facing text."""
    text = (
        "Based on the live tool results from your uploaded documents, I "
        "found one matching document: [ingested] other.txt: ATOM PHASE D "
        "FIXTURE.\n\nFrom this document, the launch code is QUARTZ-77.")
    tool = _tool_block(("l3_zephyr9_fixture.txt", "QUARTZ-77"))
    assert present_answer(text, tool, "what is the code?") == text


def test_numbered_source_shape_without_matching_evidence_is_preserved():
    text = (
        "1. [ingested] other.txt: not from the tool block.\n\n"
        "The launch code is QUARTZ-77.")
    tool = _tool_block(("l3_zephyr9_fixture.txt", "QUARTZ-77"))
    assert present_answer(text, tool, "what is the code?") == text


def test_explicit_quote_request_preserves_carrier_shaped_paragraph():
    text = (
        "Based on the live tool results, the source says: [ingested] "
        "l3_zephyr9_fixture.txt: ATOM PHASE D FIXTURE.\n\n"
        "That is the exact wording you asked for, and it is preserved in "
        "the source document for the audit.")
    tool = _tool_block(
        ("l3_zephyr9_fixture.txt", "ATOM PHASE D FIXTURE."))
    message = "Quote the source paragraph exactly, word for word."
    assert present_answer(text, tool, message) == text
    # Without the explicit quote request the same carrier is stripped.
    assert present_answer(
        text, tool, "search my documents for the fixture") != text


def test_explicit_quote_request_preserves_line_numbered_source():
    text = (
        "L1: first line\nL2: second line\n\n"
        "The quoted source is preserved here for the audit, and the answer "
        "continues with the remaining substantive explanation.")
    assert present_answer(
        text, None, "Quote the source lines verbatim.") == text
    assert "L1:" not in present_answer(
        text, None, "summarize the source")


def test_answer_bearing_line_numbered_source_is_preserved():
    """A line-numbered block may contain the only answer; do not remove it
    when the remaining text is not substantive."""
    text = (
        "L1: The launch code for project Zephyr-9 is QUARTZ-77.\n"
        "L2: Source: l3_zephyr9_fixture.txt.\n\n"
        "That is the answer.")
    clean = present_answer(text, None, "what is the code?")
    assert "QUARTZ-77" in clean
    assert "That is the answer." in clean


def test_answer_bearing_line_numbered_with_long_tail_is_preserved():
    text = (
        "L1: The launch code for project Zephyr-9 is QUARTZ-77.\n"
        "L2: Source: l3_zephyr9_fixture.txt.\n\n" + _LONG_TAIL)
    clean = present_answer(text, None, "what is the code?")
    assert "QUARTZ-77" in clean
    assert _LONG_TAIL in clean


@pytest.mark.parametrize("value", ["$48,000.00", "48%"])
def test_answer_bearing_line_numbered_money_or_percent_is_preserved(value):
    text = (
        f"L1: The recorded value is {value}.\n"
        "L2: Source: notes.txt.\n\n" + _LONG_TAIL)
    clean = present_answer(text, None, "what is the value?")
    assert value in clean
    assert _LONG_TAIL in clean


def test_line_numbered_value_superstring_does_not_mask_the_answer():
    text = (
        "L1: The launch code is QUARTZ-77.\n"
        "L2: Source: notes.txt.\n\n"
        "The reference code QUARTZ-770 appears in the archive, and the "
        "document is stored in the workspace for review and audit.")
    clean = present_answer(text, None, "what is the code?")
    assert "QUARTZ-77" in clean


def test_line_numbered_hyphenated_prose_is_not_an_answer_value():
    text = (
        "L1: This is a well-known state-of-the-art approach.\n"
        "L2: Source: notes.txt.\n\n" + _LONG_TAIL)
    clean = present_answer(text, None, "summarize the source")
    assert "well-known" not in clean
    assert _LONG_TAIL in clean


def test_carrier_without_evidence_origin_is_preserved():
    """No tool block means no positive origin. Preserve the paragraph
    rather than deleting user-facing text on a structural lookalike."""
    inline = (
        "Based on the live tool results, I found one matching document: "
        "[ingested] l3_zephyr9_fixture.txt: ATOM PHASE D FIXTURE.\n\n"
        "The launch code is QUARTZ-77.")
    numbered = (
        "1. [ingested] l3_zephyr9_fixture.txt: ATOM PHASE D FIXTURE.\n\n"
        "The launch code is QUARTZ-77.")
    assert present_answer(inline, None, "what is the code?") == inline
    assert present_answer(numbered, None, "what is the code?") == numbered


def test_captured_attempt8_hybrid_carrier_keeps_the_answer():
    """The served attempt-8 L3 answer introduced the source in paragraph
    two as ``From [ingested] <source>: ...`` but that same paragraph also
    contains the answer. Remove the carrier prefix, keep the body."""
    served = CAPTURED8["steps"]["l3"]["initial_response"]["message"]
    tool = _tool_block(
        ("l3_zephyr9_fixture.txt",
         "ATOM PHASE D FIXTURE — internal notes, I found:\n"
         '"The launch code for project Zephyr-9 is QUARTZ-77."'))
    clean = present_answer(served, tool, L3_ASK)
    assert "From [ingested]" not in clean
    assert "QUARTZ-77" in clean
    assert "ATOM PHASE D FIXTURE — internal notes" in clean


def test_numbered_hybrid_carrier_is_preserved():
    """A numbered paragraph that quotes the answer is hybrid, not a pure
    carrier. Preserve it rather than deleting the answer."""
    text = (
        "Here is what I found.\n\n"
        "1. [ingested] l3_zephyr9_fixture.txt: ATOM PHASE D FIXTURE — "
        "internal notes, I found:\n"
        '"The launch code for project Zephyr-9 is QUARTZ-77."\n\n'
        "The source is l3_zephyr9_fixture.txt.")
    tool = _tool_block(
        ("l3_zephyr9_fixture.txt",
         "ATOM PHASE D FIXTURE — internal notes, I found:\n"
         '"The launch code for project Zephyr-9 is QUARTZ-77."'))
    clean = present_answer(text, tool, "what is the code?")
    assert "QUARTZ-77" in clean
    assert "The source is l3_zephyr9_fixture.txt." in clean


def test_later_numbered_carrier_prefix_is_removed_body_retained():
    text = (
        "Sure, here is what I found.\n\n"
        "1. [ingested] l3_zephyr9_fixture.txt: ATOM PHASE D FIXTURE.\n\n"
        "The launch code for project Zephyr-9 is QUARTZ-77, according to "
        "the stored document.")
    tool = _tool_block(
        ("l3_zephyr9_fixture.txt", "ATOM PHASE D FIXTURE."))
    clean = present_answer(text, tool, "what is the code?")
    assert "1. [ingested]" not in clean
    assert "Sure, here is what I found." in clean
    assert "QUARTZ-77" in clean


def test_explanation_naming_a_real_source_is_preserved():
    """A source label alone is not a carrier. Explanatory prose that names
    a retrieved file must not be deleted or replaced by the limitation."""
    tool = _tool_block(
        ("l3_zephyr9_fixture.txt", "ATOM PHASE D FIXTURE."))
    text = (
        "1. [ingested] l3_zephyr9_fixture.txt: this tag means the file was "
        "imported, not authored.\n\n"
        "2. [vector] l3_zephyr9_fixture.txt: this tag means the file was "
        "embedded.")
    assert present_answer(text, tool, "explain the tags") == text


def test_marker_mismatch_is_preserved():
    """A [vector] explanation must not match an [ingested] tool line."""
    tool = _tool_block(("notes.txt", "notes body"))
    text = (
        "1. [vector] notes.txt: it means the file was embedded.\n\n"
        "Second paragraph.")
    assert present_answer(text, tool, "explain the marker") == text


def test_answer_bearing_numbered_carrier_keeps_body():
    """The paragraph contains the only answer; the prefix goes, body stays."""
    text = (
        "Here is what I found.\n\n"
        "1. [ingested] l3_zephyr9_fixture.txt: The launch code for project "
        "Zephyr-9 is QUARTZ-77.\n\n"
        "I hope that helps.")
    tool = _tool_block(
        ("l3_zephyr9_fixture.txt",
         "The launch code for project Zephyr-9 is QUARTZ-77."))
    clean = present_answer(text, tool, "what is the code?")
    assert "[ingested]" not in clean
    assert "QUARTZ-77" in clean
    assert "I hope that helps." in clean


def test_answer_bearing_inline_carrier_keeps_body():
    text = (
        "Based on the live tool results, I found: [ingested] "
        "l3_zephyr9_fixture.txt: The launch code for project Zephyr-9 is "
        "QUARTZ-77.\n\nI hope that helps.")
    tool = _tool_block(
        ("l3_zephyr9_fixture.txt",
         "The launch code for project Zephyr-9 is QUARTZ-77."))
    clean = present_answer(text, tool, "what is the code?")
    assert "[ingested]" not in clean
    assert "QUARTZ-77" in clean
    assert "I hope that helps." in clean


_LONG_TAIL = (
    "The document is stored in the workspace and can be opened from the "
    "documents panel, which lists all uploaded files and their metadata "
    "for review and audit purposes.")


def test_answer_bearing_numbered_carrier_long_tail_keeps_body():
    text = (
        "Here is what I found.\n\n"
        "1. [ingested] l3_zephyr9_fixture.txt: The launch code for project "
        "Zephyr-9 is QUARTZ-77.\n\n" + _LONG_TAIL)
    tool = _tool_block(
        ("l3_zephyr9_fixture.txt",
         "The launch code for project Zephyr-9 is QUARTZ-77."))
    clean = present_answer(text, tool, "what is the code?")
    assert "[ingested]" not in clean
    assert "QUARTZ-77" in clean
    assert _LONG_TAIL in clean


def test_answer_bearing_inline_carrier_long_tail_keeps_body():
    text = (
        "Based on the live tool results, I found: [ingested] "
        "l3_zephyr9_fixture.txt: The launch code for project Zephyr-9 is "
        "QUARTZ-77.\n\n" + _LONG_TAIL)
    tool = _tool_block(
        ("l3_zephyr9_fixture.txt",
         "The launch code for project Zephyr-9 is QUARTZ-77."))
    clean = present_answer(text, tool, "what is the code?")
    assert "[ingested]" not in clean
    assert "QUARTZ-77" in clean
    assert _LONG_TAIL in clean


def test_two_answer_bearing_carriers_keep_the_answer():
    text = (
        "1. [ingested] l3_zephyr9_fixture.txt: ATOM PHASE D FIXTURE.\n\n"
        "2. [ingested] l3_zephyr9_fixture.txt: The launch code for project "
        "Zephyr-9 is QUARTZ-77.\n\n" + _LONG_TAIL)
    tool = _tool_block(
        ("l3_zephyr9_fixture.txt",
         "ATOM PHASE D FIXTURE. The launch code for project Zephyr-9 is "
         "QUARTZ-77."))
    clean = present_answer(text, tool, "what is the code?")
    assert "[ingested]" not in clean
    assert "QUARTZ-77" in clean


def test_prefix_answer_is_not_lost_with_the_marker():
    """If the answer value sits before the marker, keep the prefix too."""
    text = (
        "Based on the live tool results, the launch code is QUARTZ-77: "
        "[ingested] notes.txt: ATOM PHASE D FIXTURE.\n\n" + _LONG_TAIL)
    tool = _tool_block(("notes.txt", "ATOM PHASE D FIXTURE."))
    clean = present_answer(text, tool, "what is the code?")
    assert "[ingested]" not in clean
    assert "QUARTZ-77" in clean
    assert "notes.txt: ATOM PHASE D FIXTURE" in clean


def test_source_label_answer_is_retained():
    """The source label is kept, so 'which document?' is still answered."""
    text = (
        "1. [ingested] notes.txt: ATOM PHASE D FIXTURE.\n\n" + _LONG_TAIL)
    tool = _tool_block(("notes.txt", "ATOM PHASE D FIXTURE."))
    clean = present_answer(text, tool, "which document has the fixture?")
    assert "[ingested]" not in clean
    assert "notes.txt: ATOM PHASE D FIXTURE" in clean


def test_single_quoted_answer_prefix_is_removed_body_retained():
    text = (
        "1. [ingested] l3_zephyr9_fixture.txt: 'The approved color is "
        "blue.'\n\n" + _LONG_TAIL)
    tool = _tool_block(
        ("l3_zephyr9_fixture.txt", "The approved color is blue."))
    clean = present_answer(text, tool, "what is the approved color?")
    assert "The approved color is blue." in clean


@pytest.mark.parametrize("message", [
    "Quote the line item price in the draft.",
    "Quote the following line item price in the draft.",
    "Quote the next line item total.",
    "Quote the document total in the draft.",
    "Quote the note's balance.",
])
def test_business_quote_phrase_does_not_disable_stripping(message):
    text = (
        "Based on the live tool results, I found: [ingested] "
        "l3_zephyr9_fixture.txt: ATOM PHASE D FIXTURE.\n\n" + _LONG_TAIL)
    tool = _tool_block(
        ("l3_zephyr9_fixture.txt", "ATOM PHASE D FIXTURE."))
    clean = present_answer(text, tool, message)
    assert "[ingested]" not in clean
    assert "ATOM PHASE D FIXTURE" in clean
    assert _LONG_TAIL in clean


def test_what_does_the_note_say_preserves_carrier_shape():
    text = (
        "Based on the live tool results, I found: [ingested] "
        "l3_zephyr9_fixture.txt: ATOM PHASE D FIXTURE.\n\n" + _LONG_TAIL)
    tool = _tool_block(
        ("l3_zephyr9_fixture.txt", "ATOM PHASE D FIXTURE."))
    assert present_answer(text, tool, "What does the note say?") == text


def test_single_paragraph_carrier_prefix_is_removed():
    """Even a standalone carrier keeps its body; only the marker prefix is
    removed, so the turn never loses the only text it has."""
    text = "1. [ingested] l3_zephyr9_fixture.txt: ATOM PHASE D FIXTURE."
    tool = _tool_block(
        ("l3_zephyr9_fixture.txt", "ATOM PHASE D FIXTURE."))
    clean = present_answer(text, tool, "what is the fixture?")
    assert "[ingested]" not in clean
    assert "ATOM PHASE D FIXTURE" in clean


def test_quoted_source_body_is_retained():
    """The quoted body is kept; only the carrier prefix is removed."""
    text = (
        '1. [ingested] l3_zephyr9_fixture.txt: "ATOM PHASE D FIXTURE — '
        'internal notes."\n\n' + _LONG_TAIL)
    tool = _tool_block(
        ("l3_zephyr9_fixture.txt",
         '"ATOM PHASE D FIXTURE — internal notes."'))
    clean = present_answer(text, tool, "what does the fixture say?")
    assert "[ingested]" not in clean
    assert '"ATOM PHASE D FIXTURE — internal notes."' in clean


def test_short_body_is_not_treated_as_carrier():
    """A short body can be the only answer; it is not stripped."""
    text = "1. [ingested] l3_zephyr9_fixture.txt: QUARTZ-77\n\n" + _LONG_TAIL
    tool = _tool_block(("l3_zephyr9_fixture.txt", "QUARTZ-77"))
    assert present_answer(text, tool, "what is the code?") == text


def test_business_quote_noun_does_not_disable_excerpt_stripping():
    """A question about whether a quote matches is not a request to
    reproduce text; the internal line-numbered block must still be removed."""
    text = (
        "The full text of the top hit:\n"
        "L1: ATOM PHASE D FIXTURE — internal notes.\n"
        "L2: Project Zephyr-9 launch planning.\n"
        "L5: Decoy: the archive key for project Halcyon-2 is BASALT-13.\n\n"
        "The launch code for project Zephyr-9 is QUARTZ-77, according to "
        "the stored document, and the remaining explanation is substantive.")
    clean = present_answer(
        text, None, "Does the quote match the approved record?")
    assert "BASALT-13" not in clean
    assert "L1:" not in clean
    assert "QUARTZ-77" in clean


@pytest.mark.parametrize("message", [
    "Show me exactly what the document says.",
    "Give me the source text.",
    "Give me the original text of the note.",
    "Copy the source text.",
    "Repeat the paragraph.",
    "Paste the source text here.",
    "What exactly does the note say?",
    "What does the note contain?",
    "Tell me what the note contains.",
    "Quote the source paragraph exactly, word for word.",
    "Quote from the document.",
    "Quote what the document says.",
    "Quote exactly what the document says.",
    "Quote the document's first line.",
    "Quote the first line.",
    "Quote the lines below.",
    "Quote the source line 3.",
])
def test_explicit_quote_phrasings_preserve_carrier_shape(message):
    text = (
        "Based on the live tool results, I found: [ingested] "
        "l3_zephyr9_fixture.txt: ATOM PHASE D FIXTURE.\n\n"
        "That is the exact wording you asked for, and it is preserved in "
        "the source document for the audit.")
    tool = _tool_block(
        ("l3_zephyr9_fixture.txt", "ATOM PHASE D FIXTURE."))
    # The same carrier is stripped without an explicit quote request.
    assert present_answer(
        text, tool, "search my documents for the fixture") != text
    assert present_answer(text, tool, message) == text


def test_business_quote_verb_does_not_disable_excerpt_stripping():
    text = (
        "Based on the live tool results, I found: [ingested] "
        "l3_zephyr9_fixture.txt: ATOM PHASE D FIXTURE.\n\n"
        "The approved price remains unchanged in the draft, and the "
        "payment terms still say Net 45.")
    tool = _tool_block(
        ("l3_zephyr9_fixture.txt", "ATOM PHASE D FIXTURE."))
    clean = present_answer(
        text, tool, "Quote the approved price in the draft.")
    assert "[ingested]" not in clean
    assert "ATOM PHASE D FIXTURE" in clean
    assert "approved price remains unchanged" in clean


def test_explicit_quote_request_still_strips_exact_internal_envelope():
    envelope, answer = _l3_envelope_and_answer()
    clean = present_answer(
        envelope + "\n\n" + answer, envelope,
        "Quote the source paragraph exactly.")
    assert "LIVE TOOL RESULTS" not in clean
    assert "BASALT-13" not in clean
    assert "QUARTZ-77" in clean
