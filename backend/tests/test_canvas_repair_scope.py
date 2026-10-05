"""F02 — the bounded-repair scope fence, and the intended-change verifier.

Two defects, both reproduced on this source and both in
`core/chat_canvas_editor.py`:

1. A BOUNDED REPAIR could widen the edit past the fields the discarded plan
   named. Reproduced end to end on the isolated candidate: a body-scoped
   request, a patch plan whose `find` was absent, and a replace-mode re-ask
   that changed `subject` — written, `postcondition_verified: true`, and
   reported to the user as a completed subject edit.

2. `_verify_intended_change` reported a landed, verified edit as UNAPPLIED
   when the replacement text CONTAINS the text it replaced, because the
   "the old text must be gone" substring test cannot discriminate there. A
   durable write was therefore reported to the user as a failure.

These are unit-level guards for the same mechanisms the acceptance run
exercises end to end; they exist so a future edit to the repair ladder cannot
re-open either hole without a failing test.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, List

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.chat_canvas_editor import (  # noqa: E402
    CanvasEditPlan,
    CanvasPatchOp,
    _changed_content_keys,
    _plan_field_scope,
    _verify_intended_change,
    repair_out_of_scope,
)

BODY_OLD = "Quote validity: 15 days."
BODY_NEW = "Quote validity: 30 days."
SUBJECT = "Quote for Steve - bandsaw WG-350DSAV"
SUBJECT_WRECKED = f"{SUBJECT} (updated)"


def _current(subject: str = SUBJECT, body: str = BODY_OLD) -> Dict[str, Any]:
    return {"to": "steve@example.com", "cc": "",
            "subject": subject,
            "body": f"<div><p><b>{body}</b></p></div>"}


def _patch(field: str, find: str, replace: str) -> List[CanvasPatchOp]:
    return [CanvasPatchOp(field=field, find=find, replace=replace)]


def _replace(plan_content: Dict[str, Any]) -> CanvasEditPlan:
    return CanvasEditPlan(
        wants_edit=True, edit_mode="replace", ops=[],
        updated_content_json=json.dumps(plan_content), reply="done")


# --------------------------------------------------------------------------
# 1. the scope fence
# --------------------------------------------------------------------------
class TestRepairScope:
    def test_widening_to_an_unnamed_field_is_refused(self):
        """The reproduced failure: `body` was in play, `subject` was not."""
        reference = CanvasEditPlan(wants_edit=True, edit_mode="patch",
                                   ops=_patch("body", BODY_OLD, BODY_NEW))
        assert repair_out_of_scope(
            _replace(_current(subject=SUBJECT_WRECKED, body=BODY_OLD)),
            reference, _current()) is not None

    def test_in_scope_repair_is_allowed(self):
        """The control that must keep working: only `body` changes."""
        reference = CanvasEditPlan(wants_edit=True, edit_mode="patch",
                                   ops=_patch("body", BODY_OLD, BODY_NEW))
        assert repair_out_of_scope(
            _replace(_current(subject=SUBJECT, body=BODY_NEW)),
            reference, _current()) is None

    def test_echoed_unchanged_keys_are_not_a_widening(self):
        """A model that returns the whole object, changing only `body`, is
        inside the fence — the echo burden is exactly why that happens."""
        reference = CanvasEditPlan(wants_edit=True, edit_mode="patch",
                                   ops=_patch("body", BODY_OLD, BODY_NEW))
        assert repair_out_of_scope(
            _replace(_current(body=BODY_NEW)), reference, _current()) is None

    def test_patch_repair_is_field_scoped_by_construction(self):
        """A repair answered with ops rather than replacement content carries
        its own field names, so there is nothing to fence."""
        reference = CanvasEditPlan(wants_edit=True, edit_mode="patch",
                                   ops=_patch("body", BODY_OLD, BODY_NEW))
        replan = CanvasEditPlan(wants_edit=True, edit_mode="patch",
                                ops=_patch("subject", SUBJECT, SUBJECT_WRECKED))
        assert repair_out_of_scope(replan, reference, _current()) is None

    def test_no_scope_known_is_not_a_violation(self):
        """The fence must not invent a scope. A reference plan with no ops,
        a whole-document op, and a per-cell op all leave the scope unknown."""
        no_ops = CanvasEditPlan(wants_edit=True, edit_mode="replace",
                                updated_content_json=json.dumps(
                                    _current(subject=SUBJECT_WRECKED)))
        assert repair_out_of_scope(_replace(_current(subject=SUBJECT_WRECKED)),
                                   no_ops, _current()) is None

        whole_doc = CanvasEditPlan(
            wants_edit=True, edit_mode="patch",
            ops=[CanvasPatchOp(field=None, find=BODY_OLD, replace=BODY_NEW)])
        assert repair_out_of_scope(_replace(_current(subject=SUBJECT_WRECKED)),
                                   whole_doc, _current()) is None

        per_cell = CanvasEditPlan(
            wants_edit=True, edit_mode="patch",
            ops=[CanvasPatchOp(field=None, cell="B2", find="1", replace="2")])
        assert repair_out_of_scope(_replace(_current(subject=SUBJECT_WRECKED)),
                                   per_cell, _current()) is None

    def test_non_key_scoped_payload_is_not_judged(self):
        """Grid/list content has no keys to widen, so the fence abstains."""
        reference = CanvasEditPlan(wants_edit=True, edit_mode="patch",
                                   ops=_patch("body", BODY_OLD, BODY_NEW))
        assert repair_out_of_scope(
            _replace([["a", "b"]]), reference, [["a", "b"]]) is None

    def test_no_change_at_all_is_never_a_widening(self):
        reference = CanvasEditPlan(wants_edit=True, edit_mode="patch",
                                   ops=_patch("body", BODY_OLD, BODY_NEW))
        assert repair_out_of_scope(_replace(_current()), reference,
                                   _current()) is None

    def test_undecodable_payload_is_left_to_the_existing_ladder(self):
        """A payload this module cannot parse is not adjudicated here; the
        decode ladder in apply_canvas_edit already refuses it."""
        reference = CanvasEditPlan(wants_edit=True, edit_mode="patch",
                                   ops=_patch("body", BODY_OLD, BODY_NEW))
        broken = CanvasEditPlan(wants_edit=True, edit_mode="replace", ops=[],
                                updated_content_json="{not json at all")
        assert repair_out_of_scope(broken, reference, _current()) is None

    def test_helpers_are_honest_about_unknown(self):
        assert _plan_field_scope(None) is None
        assert _plan_field_scope(CanvasEditPlan()) is None
        assert _changed_content_keys("text", _current()) is None
        assert _changed_content_keys({"rows": [[1]]},
                                     {"rows": [[1]]}) is None
        assert _changed_content_keys({"body": "x"}, _current()) == {"body"}


# --------------------------------------------------------------------------
# 2. the intended-change verifier
# --------------------------------------------------------------------------
class TestVerifyIntendedChange:
    def test_replacement_superset_of_find_is_applied(self):
        """The reproduced false negative: replacing X with X (updated) leaves
        X present, and the write really did land."""
        plan = CanvasEditPlan(
            wants_edit=True, edit_mode="patch",
            ops=_patch("subject", SUBJECT, SUBJECT_WRECKED))
        readback = _current(subject=SUBJECT_WRECKED)
        got = _verify_intended_change(plan, readback, content_persisted=True)
        assert got["all_intended_applied"] is True, got
        assert got["unapplied_ops"] == []

    def test_a_genuinely_unreplaced_target_still_fails(self):
        """The check keeps its teeth where it CAN discriminate: the old text
        survives and the replacement does not."""
        plan = CanvasEditPlan(
            wants_edit=True, edit_mode="patch",
            ops=_patch("body", BODY_OLD, BODY_NEW))
        got = _verify_intended_change(plan, _current(), content_persisted=True)
        assert got["all_intended_applied"] is False
        assert any("replacement text is absent" in m
                   for m in got["unapplied_ops"]), got

    def test_identical_find_and_replace_is_not_a_failure(self):
        plan = CanvasEditPlan(
            wants_edit=True, edit_mode="patch",
            ops=_patch("body", BODY_OLD, BODY_OLD))
        got = _verify_intended_change(plan, _current(), content_persisted=True)
        assert got["all_intended_applied"] is True, got

    def test_verification_is_scoped_to_the_named_field(self):
        """`30 days` somewhere else in the document must not satisfy a body
        edit — the F05 'new text already exists elsewhere' control."""
        plan = CanvasEditPlan(
            wants_edit=True, edit_mode="patch",
            ops=_patch("body", BODY_OLD, BODY_NEW))
        readback = _current(body=f"<p>see the 30 days clause</p>")
        got = _verify_intended_change(plan, readback, content_persisted=True)
        assert got["all_intended_applied"] is False
        assert got["scope"] == "field"

    def test_replace_mode_still_needs_the_content_persisted(self):
        plan = _replace(_current(body=BODY_NEW))
        assert _verify_intended_change(plan, _current(body=BODY_NEW),
                                       content_persisted=True)[
                                           "all_intended_applied"] is True
        assert _verify_intended_change(plan, _current(body=BODY_NEW),
                                       content_persisted=False)[
                                           "all_intended_applied"] is False

    def test_a_plan_with_no_work_has_no_intended_change(self):
        plan = CanvasEditPlan(wants_edit=True, edit_mode="patch", ops=[])
        got = _verify_intended_change(plan, _current(), content_persisted=True)
        assert got["all_intended_applied"] is False
        assert got["checked"] == 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(pytest.main([__file__, "-q"]))


class TestJobFindingsSection:
    """Round 62 (authorized drafting): the job's durable research record
    reaches the edit planner — verified findings with sources, open
    decisions that must stay annotated, manual values preserved,
    freshness limits kept out of customer-facing text."""

    def test_section_carries_findings_and_rules(self):
        from core.chat_canvas_editor import _job_findings_section
        out = _job_findings_section({
            "verified": [
                {"item": "No. 381",
                 "note": "workbook labels PRICE=3297 (2019 copy)",
                 "source": "job ledger"}],
            "open_decisions": [
                {"item": "U-22",
                 "question": "List Price=1431 vs List Price_2=1393"}],
            "manual_preserved": ["No. 381: $2,902 (owner-approved)"],
            "freshness_limits": ["SLE24-16: saved-copy; live unverified"],
        })
        assert "No. 381" in out and "PRICE=3297" in out
        assert "UNRESOLVED U-22" in out and "do NOT silently pick" in out
        assert "$2,902" in out and "preserve exactly" in out
        assert "FRESHNESS LIMITS" in out
        assert "OUT of customer-facing text" in out.replace(
            "customer-facing text", "customer-facing text")

    def test_section_none_and_empty(self):
        from core.chat_canvas_editor import _job_findings_section
        assert _job_findings_section(None) == ""
        assert _job_findings_section({}) == ""
        assert _job_findings_section({"verified": []}) == ""

    def test_plan_accepts_job_findings(self):
        # plan_canvas_edit's signature carries the parameter (default
        # None keeps every existing caller compatible).
        import inspect
        from core.chat_canvas_editor import plan_canvas_edit
        sig = inspect.signature(plan_canvas_edit)
        assert "job_findings" in sig.parameters
        assert sig.parameters["job_findings"].default is None
