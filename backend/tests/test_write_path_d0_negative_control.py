"""D0 negative control: the tool says success, persistence does not happen.

This is the exact shape of the 2026-09-27 incident. The canvas edit planner
produced a plan, the write tool returned `success: True`, and the user was shown

    **Canvas Updated:**   | Body | Quote validity: **30 days**. |

while `canvas_audit` held no row for any canvas in 30 minutes and no canvas in
the world contained the new text. A success claim with no verified write.

The control pins the behaviour that must hold from now on: when the store
reports success but the durable canvas does not contain what was written, the
turn must NOT claim the canvas was updated. Not with a softened message, not
with a disclaimer appended underneath -- it must not claim it at all, because
appending a disclaimer to a fabricated success is what the incident did.

Run directly, or under pytest:

    python backend/tests/test_write_path_d0_negative_control.py
"""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

BACKEND = Path(__file__).resolve().parents[1]
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from core.chat_canvas_editor import (  # noqa: E402
    CanvasEditPlan,
    CanvasPatchOp,
    apply_canvas_edit,
)

ORIGINAL = {"type": "doc", "content": "Quote validity: 15 days."}
INTENDED = {"type": "doc", "content": "Quote validity: 30 days."}

#: Phrases that would make this a success claim again. "nothing is confirmed"
#: style wording is deliberately NOT in this list: the incident's reply carried a
#: disclaimer AND a false success, so the test must fail on the success, not be
#: satisfied by hedging.
SUCCESS_PHRASES = (
    "canvas updated", "**canvas updated", "i updated", "i've updated",
    "i have updated", "updated the canvas", "successfully updated",
    "i'll update", "i will update", "the edit has been applied",
    "quote validity: **30 days**", "quote validity: 30 days",
)


def _canvas():
    return {"canvas_id": "c-d0", "canvas_type": "document", "title": "Draft",
            "content": ORIGINAL}


def _plan():
    return CanvasEditPlan(wants_edit=True,
                          updated_content_json=json.dumps(INTENDED),
                          title="Draft v2",
                          reply="Updated the quote validity to 30 days.")


class D0NegativeControl(unittest.TestCase):
    """Tool reports success; durable store disagrees. No success may be claimed."""

    def _apply_with_lying_store(self):
        """Write tool says OK. Read-back returns the ORIGINAL, unchanged."""

        async def _update(user_id, canvas_id, content, canvas_type=None,
                          title=None, **kwargs):
            # The tool's own claim: success.
            return {"success": True, "audit_id": "audit-lies"}

        async def _read(user_id, canvas_id, **kwargs):
            # The durable truth: nothing was written.
            return {"success": True, "canvas_id": canvas_id,
                    "canvas_type": "document", "title": "Draft",
                    "content": ORIGINAL}

        with patch("tools.canvas_crud_tool.update_canvas_content",
                   new=AsyncMock(side_effect=_update)), \
             patch("tools.canvas_crud_tool.read_canvas",
                   new=AsyncMock(side_effect=_read)):
            return _apply_with_lying_store.result

    def test_editor_refuses_to_report_success_when_readback_disagrees(self):
        async def _run():
            with patch("tools.canvas_crud_tool.update_canvas_content",
                       new=AsyncMock(side_effect=_update_ok)), \
                 patch("tools.canvas_crud_tool.read_canvas",
                       new=AsyncMock(side_effect=_read_unchanged)):
                return await apply_canvas_edit(_plan(), "user-1", _canvas())
        result = asyncio_run(_run())

        self.assertIsNotNone(result, "apply returned nothing at all")
        # The load-bearing assertion: NOT a success.
        self.assertFalse(
            result.get("success"),
            "apply_canvas_edit reported success although the durable canvas "
            f"never changed: {json.dumps(result)[:300]}")
        self.assertIs(
            result.get("postcondition_verified"), False,
            "an unverified write must be recorded as unverified, not omitted")
        self.assertIn("postcondition_error", result)
        # Distinction preserved for reconciliation: the write was ATTEMPTED and
        # the tool claimed it happened. Collapsing that to a plain failure would
        # lose the only evidence that an audit id may exist.
        self.assertTrue(result.get("write_recorded"),
                        "an unverified write must stay distinguishable from a "
                        "rejected one, or reconciliation cannot find its audit row")

    def test_verified_write_still_succeeds(self):
        """The control must not be satisfied by simply refusing everything."""

        async def _run():
            with patch("tools.canvas_crud_tool.update_canvas_content",
                       new=AsyncMock(side_effect=_update_ok)), \
                 patch("tools.canvas_crud_tool.read_canvas",
                       new=AsyncMock(side_effect=_read_written)):
                return await apply_canvas_edit(_plan(), "user-1", _canvas())
        result = asyncio_run(_run())
        self.assertTrue(result.get("success"),
                        f"a genuinely persisted edit must still succeed: "
                        f"{json.dumps(result)[:300]}")
        self.assertIs(result.get("postcondition_verified"), True)

    def test_no_reply_text_can_assert_the_change(self):
        """Even the planner's own success text must not survive unverified.

        The incident's user-visible reply was the planner's text, so the text is
        part of the defect, not decoration around it.
        """
        async def _run():
            with patch("tools.canvas_crud_tool.update_canvas_content",
                       new=AsyncMock(side_effect=_update_ok)), \
                 patch("tools.canvas_crud_tool.read_canvas",
                       new=AsyncMock(side_effect=_read_unchanged)):
                return await apply_canvas_edit(_plan(), "user-1", _canvas())
        result = asyncio_run(_run())
        self.assertIsNotNone(result)
        # Whatever text comes back must not read as a completed change. The
        # editor itself does not produce the user-facing reply, so this asserts
        # the SUCCESS FLAG is the thing that carries the claim, and that the
        # plan's own reply is not smuggled through as verified output.
        if not result.get("success"):
            blob = json.dumps(result).lower()
            for phrase in ("canvas updated", "successfully updated"):
                self.assertNotIn(phrase, blob,
                                 f"unverified result still asserts {phrase!r}")


class VerificationBindingNegativeControl(unittest.TestCase):
    """Content equality alone does not prove the INTENDED change.

    The qualification that turned D0 from a necessary condition into a
    sufficient one: `readback == new_content` proves the right bytes are stored,
    not that they are the change the user asked for. Each case below is a way
    for equality to hold while the intent was not achieved, or for the effect to
    land somewhere it should not have.
    """

    def _apply(self, plan, readback_content, readback_id="c-d0",
               canvas_content=None):
        """Drive a REAL apply, varying only what the durable read-back returns.

        `canvas_content` defaults to the plan's own starting point so the ops
        match and the write genuinely proceeds. A fixture whose ops do not match
        returns None before any write, which would test nothing.
        """
        canvas = (_canvas() if canvas_content is None
                  else {"canvas_id": "c-d0", "canvas_type": "document",
                        "title": "Draft", "content": canvas_content})

        async def _run():
            with patch("tools.canvas_crud_tool.update_canvas_content",
                       new=AsyncMock(side_effect=_update_ok)), \
                 patch("tools.canvas_crud_tool.read_canvas",
                       new=AsyncMock(side_effect=_read_custom(
                           readback_content, readback_id))):
                return await apply_canvas_edit(plan, "user-1", canvas)
        return asyncio_run(_run())

    def test_wrong_canvas_is_rejected(self):
        """The read-back must be of the canvas that was edited."""
        result = self._apply(_plan(), INTENDED, readback_id="c-SOMEONE-ELSE")
        self.assertFalse(result.get("success"),
                         "a read-back of a different canvas must not verify")
        binding = result.get("postcondition_binding") or {}
        self.assertFalse(binding.get("right_canvas"),
                         f"wrong canvas was not detected: {binding}")
        self.assertEqual(binding.get("canvas_id_read_back"), "c-SOMEONE-ELSE")

    def test_partial_write_is_rejected(self):
        """Some of the intended change landing is not the intended change.

        The fixture is self-consistent on purpose: the canvas contains BOTH
        texts the plan replaces, and both ops match, so the write genuinely
        proceeds. Only the READ-BACK differs -- one field landed, the other did
        not. A fixture whose ops failed to match would return None before any
        write and would prove nothing about verification.
        """
        canvas_text = "Quote validity: 15 days. Terms: 30 day."
        plan = CanvasEditPlan(
            wants_edit=True,
            ops=[CanvasPatchOp(find="Quote validity: 15 days.",
                               replace="Quote validity: 30 days."),
                 CanvasPatchOp(find="Terms: 30 day.",
                               replace="Terms: 45 day.")])
        # Only the FIRST op landed.
        partial = canvas_text.replace("Quote validity: 15 days.",
                                      "Quote validity: 30 days.")
        result = self._apply(plan, partial, canvas_content=canvas_text)
        self.assertIsNotNone(result, "the write must have been attempted")
        self.assertFalse(result.get("success"),
                         "a partial write must not verify as a completed edit")
        fields = (result.get("postcondition_binding") or {}).get("fields") or {}
        self.assertFalse(fields.get("all_intended_applied"))
        self.assertTrue(fields.get("unapplied_ops"),
                        "the unapplied op must be named, not just counted")

    def test_incidental_text_does_not_satisfy_the_intended_change(self):
        """The target text existing elsewhere is not the change being made.

        The field the op named must carry the replacement. Here the document
        mentions "30 days" in `subject` while `body` is untouched, which is
        exactly the shape a document-wide substring check would pass.
        """
        canvas_doc = {"to": "steve@example.com",
                      "subject": "Quote",
                      "body": "<div>Quote validity: 15 days.</div>"}
        plan = CanvasEditPlan(
            wants_edit=True,
            ops=[CanvasPatchOp(field="body",
                               find="Quote validity: 15 days.",
                               replace="Quote validity: 30 days.")])
        decoy = {"to": "steve@example.com",
                 "subject": "Quote (valid 30 days from issue)",
                 "body": "<div>Quote validity: 15 days.</div>"}
        result = self._apply(plan, decoy, canvas_content=canvas_doc)
        self.assertIsNotNone(result, "the write must have been attempted")
        self.assertFalse(
            result.get("success"),
            "target text present in another field must not verify the edit")
        fields = (result.get("postcondition_binding") or {}).get("fields") or {}
        self.assertEqual(fields.get("scope"), "field",
                         "the check must be scoped to the named field")

    def test_concurrent_update_is_rejected(self):
        """A write that raced another change must not verify."""
        async def _update_conflict(user_id, canvas_id, content, canvas_type=None,
                                   title=None, **kwargs):
            return {"success": True, "audit_id": "audit-raced",
                    "conflict": True}

        async def _run():
            with patch("tools.canvas_crud_tool.update_canvas_content",
                       new=AsyncMock(side_effect=_update_conflict)), \
                 patch("tools.canvas_crud_tool.read_canvas",
                       new=AsyncMock(side_effect=_read_custom(INTENDED, "c-d0"))):
                return await apply_canvas_edit(_plan(), "user-1", _canvas())
        result = asyncio_run(_run())
        # The store reports success, so the early conflict branch is not taken;
        # the revision binding is what has to catch it.
        self.assertIs(result.get("postcondition_verified"), False,
                      "a concurrent change must fail the revision binding")
        binding = result.get("postcondition_binding") or {}
        self.assertFalse(binding.get("revision_unchanged"),
                         f"the race was not detected: {binding}")

    def test_no_audit_id_means_no_verified_operation(self):
        """Success must be bound to an operation the store actually recorded."""
        async def _update_no_audit(user_id, canvas_id, content, canvas_type=None,
                                   title=None, **kwargs):
            return {"success": True}          # no audit_id

        async def _run():
            with patch("tools.canvas_crud_tool.update_canvas_content",
                       new=AsyncMock(side_effect=_update_no_audit)), \
                 patch("tools.canvas_crud_tool.read_canvas",
                       new=AsyncMock(side_effect=_read_custom(INTENDED, "c-d0"))):
                return await apply_canvas_edit(_plan(), "user-1", _canvas())
        result = asyncio_run(_run())
        self.assertFalse(result.get("success"),
                         "a write with no audit id must not verify")
        binding = result.get("postcondition_binding") or {}
        self.assertFalse(binding.get("operation_bound"),
                         f"the missing operation was not detected: {binding}")

    def test_a_plan_asking_for_nothing_cannot_succeed(self):
        """No ops and no declared content means nothing was asked for."""
        empty = CanvasEditPlan(wants_edit=True, reply="All done!")
        async def _run():
            with patch("tools.canvas_crud_tool.update_canvas_content",
                       new=AsyncMock(side_effect=_update_ok)), \
                 patch("tools.canvas_crud_tool.read_canvas",
                       new=AsyncMock(side_effect=_read_custom(ORIGINAL, "c-d0"))):
                return await apply_canvas_edit(empty, "user-1", _canvas())
        result = asyncio_run(_run())
        self.assertIsNone(result,
                          "an empty plan must not reach the store at all")


class InconsistentPlanControl(unittest.TestCase):
    """D4: `wants_edit=False` with nonempty operations is a contradiction.

    Not a decline, and not permission. It gets ONE bounded repair through the
    existing structured-planning mechanism. Two properties matter equally: a
    self-contradictory plan is not thrown away, and operations are never
    executed merely because they are present.
    """

    def _plan_llm(self, *returns):
        from core.chat_canvas_editor import CanvasEditPlan as P
        seq = list(returns)

        async def _plan(message, history, canvas, llm, **kwargs):
            return seq.pop(0) if seq else None
        return _plan, seq

    def _run(self, plans, canvas_content="Quote validity: 15 days."):
        from core.chat_canvas_editor import plan_canvas_edit as _plan_fn
        canvas = {"canvas_id": "c-d4", "canvas_type": "document",
                  "title": "Draft", "content": canvas_content}
        calls = []

        async def _structured(llm_service, prompt, response_model,
                              system_instruction=None, **kwargs):
            calls.append(prompt)
            return plans[len(calls) - 1]

        import core.chat_canvas_editor as cce
        orig = cce._plan_structured
        cce._plan_structured = _structured
        try:
            import asyncio as _a
            return _a.run(_plan_fn(
                "change the quote validity to 30 days", [], canvas,
                object())), calls
        finally:
            cce._plan_structured = orig

    def test_inconsistent_plan_gets_one_bounded_repair(self):
        from core.chat_canvas_editor import CanvasEditPlan, CanvasPatchOp
        inconsistent = CanvasEditPlan(
            wants_edit=False,
            ops=[CanvasPatchOp(find="Quote validity: 15 days.",
                               replace="Quote validity: 30 days.")],
            reply="no edit")
        consistent = CanvasEditPlan(
            wants_edit=True,
            ops=[CanvasPatchOp(find="Quote validity: 15 days.",
                               replace="Quote validity: 30 days.")],
            reply="done")
        result, calls = self._run([inconsistent, consistent])
        self.assertEqual(len(calls), 2,
                         "an inconsistent plan must take exactly one repair")
        self.assertTrue(result.wants_edit,
                        "the repair's consistent answer must be honoured")
        self.assertIn("self-contradictory", calls[1].lower(),
                      "the repair must name the contradiction")

    def test_repair_that_also_declines_is_still_a_decline(self):
        from core.chat_canvas_editor import CanvasEditPlan, CanvasPatchOp
        a = CanvasEditPlan(wants_edit=False,
                           ops=[CanvasPatchOp(find="x", replace="y")])
        b = CanvasEditPlan(wants_edit=False, reply="still no")
        result, calls = self._run([a, b])
        self.assertEqual(len(calls), 2, "the repair is bounded to one attempt")
        self.assertFalse(result.wants_edit,
                         "a repair that declines must not become an edit")
        self.assertFalse(result.ops,
                         "a declining plan must not carry operations forward")

    def test_operations_alone_do_not_authorise_an_edit(self):
        """The whole point: ops present is not permission."""
        from core.chat_canvas_editor import CanvasEditPlan, CanvasPatchOp
        inconsistent = CanvasEditPlan(
            wants_edit=False,
            ops=[CanvasPatchOp(find="Quote validity: 15 days.",
                               replace="Quote validity: 30 days.")])
        declined = CanvasEditPlan(wants_edit=False, reply="no")
        result, _ = self._run([inconsistent, declined])
        self.assertFalse(result.wants_edit)
        self.assertFalse(result.ops,
                         "operations must not survive as an executable plan "
                         "when the planner says this is not an edit")

    def test_a_clean_decline_is_not_repaired(self):
        """No operations and no declared content means a real decline.

        Spending a second model call on an honest "no" would be a cost and a
        latency regression on every non-edit canvas turn.
        """
        from core.chat_canvas_editor import CanvasEditPlan
        result, calls = self._run([CanvasEditPlan(wants_edit=False,
                                                  reply="not an edit")])
        self.assertEqual(len(calls), 1,
                         "a consistent decline must not trigger a repair")
        self.assertFalse(result.wants_edit)


def _read_custom(content, canvas_id):
    async def _read(user_id, cid, **kwargs):
        return {"success": True, "canvas_id": canvas_id,
                "canvas_type": "document", "title": "Draft", "content": content}
    return _read


async def _update_ok(user_id, canvas_id, content, canvas_type=None, title=None,
                     **kwargs):
    return {"success": True, "audit_id": "audit-real"}


async def _read_written(user_id, canvas_id, **kwargs):
    return {"success": True, "canvas_id": canvas_id, "canvas_type": "document",
            "title": "Draft", "content": INTENDED}


async def _read_unchanged(user_id, canvas_id, **kwargs):
    return {"success": True, "canvas_id": canvas_id, "canvas_type": "document",
            "title": "Draft", "content": ORIGINAL}


def asyncio_run(coro):
    import asyncio
    return asyncio.run(coro)


if __name__ == "__main__":
    unittest.main(verbosity=2)
