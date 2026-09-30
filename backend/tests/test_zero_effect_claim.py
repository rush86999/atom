"""'Nothing was changed' must be a VERIFIED claim, not a hopeful one.

The defect
Two failure paths in `async_turn_continuation` ended with the sentence
"Nothing was changed on the canvas." — the budget-exhausted path and the
attempts-exhausted path. Neither had evidence for it. An exhausted counter says
"we stopped trying"; it does not say "nothing happened". A write can land on
attempt 1 and the run can still end in a failure verdict, which is exactly the
D0 hazard one layer up: a user reading a confident zero-effect claim about a
canvas that was in fact modified.

The rule
`Nothing was changed` is emitted only when two independent observations from the
durable store agree: the canvas's audit trail has not advanced past the fork
snapshot, AND no audit row carries an operation id this continuation legitimately
owns. Anything else — a newer audit row, a matching operation row, a content
hash that moved, a canvas that could not be re-read — yields wording that
preserves the uncertainty instead of denying it.
"""
from __future__ import annotations

import os
import sys
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("TESTING", "1")

from core import async_turn_continuation as atc  # noqa: E402


def _cont(**kw):
    base = dict(continuation_id="c-1", session_id="s-1", execution_id="e-1",
                canvas={"canvas_id": "cv-1"}, snapshot_content_hash="",
                snapshot_audit_ts="")
    base.update(kw)
    return SimpleNamespace(**base)


def test_no_canvas_in_scope_is_a_verified_zero():
    ok, ev = atc._verified_zero_effect(_cont(canvas={}))
    assert ok is True
    assert "no canvas" in ev["reason"]


def test_advanced_audit_trail_means_not_zero():
    cont = _cont(snapshot_audit_ts="2026-01-01 00:00:00")
    with patch.object(atc, "_latest_audit",
                      return_value={"id": "a2", "created_at": "2026-01-02 00:00:00",
                                    "session_id": "s-1", "action_type": "update"}), \
         patch.object(atc, "_matched_operation_row", return_value=None):
        ok, ev = atc._verified_zero_effect(cont)
    assert ok is False
    assert "audit trail advanced" in ev["reason"]


def test_operation_linked_row_means_not_zero():
    cont = _cont(snapshot_audit_ts="2026-01-01 00:00:00")
    with patch.object(atc, "_latest_audit",
                      return_value={"id": "a1", "created_at": "2026-01-01 00:00:00",
                                    "session_id": "s-1", "action_type": "create"}), \
         patch.object(atc, "_matched_operation_row",
                      return_value={"audit_id": "a9", "operation_id": "c-1",
                                    "review_status": "accepted"}):
        ok, ev = atc._verified_zero_effect(cont)
    assert ok is False
    assert "operation identity" in ev["reason"]


def test_unchanged_canvas_is_a_verified_zero():
    cont = _cont(snapshot_audit_ts="2026-01-01 00:00:00")
    with patch.object(atc, "_latest_audit",
                      return_value={"id": "a1", "created_at": "2026-01-01 00:00:00",
                                    "session_id": "s-1", "action_type": "create"}), \
         patch.object(atc, "_matched_operation_row", return_value=None):
        ok, ev = atc._verified_zero_effect(cont)
    assert ok is True, ev


def test_moved_content_hash_means_not_zero():
    cont = _cont(snapshot_audit_ts="2026-01-01 00:00:00",
                 snapshot_content_hash="hash-at-fork")
    with patch.object(atc, "_latest_audit",
                      return_value={"id": "a1", "created_at": "2026-01-01 00:00:00",
                                    "session_id": "s-1", "action_type": "create"}), \
         patch.object(atc, "_matched_operation_row", return_value=None), \
         patch.object(atc, "_content_hash", return_value="hash-now-different"):
        ok, ev = atc._verified_zero_effect(cont)
    assert ok is False
    assert "content no longer matches" in ev["reason"]


def test_the_sentence_follows_the_evidence():
    """The user-facing wording is the thing under test, not just the helper."""
    cont = _cont(snapshot_audit_ts="2026-01-01 00:00:00")
    with patch.object(atc, "_latest_audit",
                      return_value={"id": "a1", "created_at": "2026-01-01 00:00:00",
                                    "session_id": "s-1", "action_type": "create"}), \
         patch.object(atc, "_matched_operation_row", return_value=None):
        said, ev = atc._zero_effect_sentence(cont)
    assert said == "Nothing was changed on the canvas."

    with patch.object(atc, "_latest_audit",
                      return_value={"id": "a2", "created_at": "2026-01-02 00:00:00",
                                    "session_id": "s-1", "action_type": "update"}), \
         patch.object(atc, "_matched_operation_row", return_value=None):
        said, ev = atc._zero_effect_sentence(cont)
    assert said != "Nothing was changed on the canvas."
    assert "could not confirm" in said, "uncertainty must be stated, not implied"
    assert ev["sentence"] == "uncertain"
