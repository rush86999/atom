"""Snapshot-versus-projection divergence: the acceptance runners must read
the canvas state the public API serves, not the `canvases.content` ACCEPTED
snapshot.

`update_canvas_content` deliberately does not mirror a `pending_review` row
into that snapshot (its docstring says so). So on a canvas whose newest
write is still under review, the snapshot holds the PRE-edit body: a
preservation assertion computed from it reports an edit as missing while
the browser renders it correctly. Observed live on fork 2233f463
(2026-10-08): snapshot `$8,880.00` + empty header, API `$8,984.00` +
subject/cc filled.

Every fixture here is a scratch sqlite in tmp_path. No live DB.
"""
import json
import os
import sqlite3
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.orchestration_acceptance import acceptance_trial_lib as L  # noqa: E402
from scripts.orchestration_acceptance import case1_quote_trials as C    # noqa: E402

PRE_BODY = ("rows 1-8 quote | No. 381 $2,902.00 | SLE24-16 $8,880.00 | "
            "Row 268 present")
POST_BODY = ("rows 1-8 quote | No. 381 $2,902.00 | SLE24-16 $8,984.00 | "
             "Row 268 present")


def _db(tmp_path, rows):
    """rows: list of (id, action_type, canvas_type, details_dict, created_at)
    plus a canvases row carrying the accepted snapshot."""
    p = tmp_path / "scratch.db"
    con = sqlite3.connect(p)
    con.execute("CREATE TABLE canvases (id VARCHAR PRIMARY KEY, "
                "content JSON, updated_at DATETIME)")
    con.execute("CREATE TABLE canvas_audit (id VARCHAR PRIMARY KEY, "
                "canvas_id VARCHAR, action_type VARCHAR, canvas_type VARCHAR, "
                "details_json JSON, created_at DATETIME)")
    return p, con


def _seed(tmp_path, snapshot_content, audit_rows, canvas_id="cv-1"):
    p, con = _db(tmp_path, audit_rows)
    con.execute("INSERT INTO canvases VALUES (?,?,?)",
                (canvas_id, json.dumps(snapshot_content), "2026-10-06T00:00:00"))
    for i, (rid, action, ctype, details, created) in enumerate(audit_rows):
        con.execute("INSERT INTO canvas_audit VALUES (?,?,?,?,?,?)",
                    (rid, canvas_id, action, ctype, json.dumps(details), created))
    con.commit()
    con.close()
    return p


SNAP = {"to": "", "cc": "", "subject": "", "body": PRE_BODY}
PENDING = {"to": "", "cc": "Vipul <vipul@brennan.ca>",
           "subject": "Requested Machinery & Alternatives", "body": POST_BODY}


def test_pending_review_row_is_projected_not_the_snapshot(tmp_path):
    db = _seed(tmp_path, SNAP, [
        ("a1", "update", "email",
         {"content": SNAP, "review_status": "accepted"}, "2026-10-06T00:55:39"),
        ("a2", "update", "email",
         {"content": PENDING, "review_status": "pending_review",
          "operation_id": "op-1"}, "2026-10-08T22:09:35"),
    ])
    p = L.canvas_projection(db, "cv-1")
    assert p["success"] and p["source"] == "audit"
    assert "$8,984.00" in p["body"], p["body"]
    assert "$8,880.00" not in p["body"]
    assert p["diverges_from_snapshot"] is True
    assert p["review_status"] == "pending_review"
    assert p["operation_id"] == "op-1"
    assert p["cc"] == "Vipul <vipul@brennan.ca>"
    assert p["subject"] == "Requested Machinery & Alternatives"


def test_the_snapshot_reader_would_have_reported_the_edit_missing(tmp_path):
    """The pin has teeth: the old reader's answer differs, and it is the
    WRONG answer for a preservation assertion."""
    db = _seed(tmp_path, SNAP, [
        ("a1", "update", "email",
         {"content": SNAP, "review_status": "accepted"}, "2026-10-06T00:55:39"),
        ("a2", "update", "email",
         {"content": PENDING, "review_status": "pending_review"},
         "2026-10-08T22:09:35"),
    ])
    old = L.sqlite_select(db, "SELECT content FROM canvases WHERE id=?",
                          ("cv-1",))[0][0]
    assert "$8,880.00" in old and "$8,984.00" not in old
    assert "$8,880.00" in C.figures_near_label(old, "SLE24-16")
    assert "$8,984.00" not in C.figures_near_label(old, "SLE24-16")
    projected = L.canvas_projection(db, "cv-1")["text"]
    assert "$8,984.00" in C.figures_near_label(projected, "SLE24-16")
    assert "$8,880.00" not in C.figures_near_label(projected, "SLE24-16")


def test_accepted_and_mirrored_row_agrees_with_the_snapshot(tmp_path):
    accepted = {"to": "", "cc": "", "subject": "", "body": POST_BODY}
    db = _seed(tmp_path, accepted, [
        ("a1", "update", "email",
         {"content": accepted, "review_status": "accepted"}, "2026-10-08T22:09:35"),
    ])
    p = L.canvas_projection(db, "cv-1")
    assert p["review_status"] == "accepted"
    assert p["diverges_from_snapshot"] is False


def test_event_stamp_falls_back_to_the_content_bearing_row(tmp_path):
    """email_send / email_send_attempt append after a send without a body;
    the trail's body is the row beneath, and the newest row still names the
    action the caller is looking at (mirrors read_canvas)."""
    db = _seed(tmp_path, SNAP, [
        ("a1", "update", "email",
         {"content": PENDING, "review_status": "pending_review"},
         "2026-10-08T22:09:35"),
        ("a2", "email_send_attempt", "email", {"to": "x@y.z"},
         "2026-10-08T22:10:00"),
    ])
    p = L.canvas_projection(db, "cv-1")
    assert p["source"] == "audit"
    assert "$8,984.00" in p["body"]
    assert p["action_type"] == "email_send_attempt"
    assert p["audit_id"] == "a1", "the body's provenance is the content row"
    assert p["review_status"] == "pending_review"


def test_legacy_canvas_with_no_audit_body_falls_back_to_the_snapshot(tmp_path):
    db = _seed(tmp_path, SNAP, [
        ("a1", "fork", "email", {"title": "created"}, "2026-10-06T00:55:39"),
    ])
    p = L.canvas_projection(db, "cv-1")
    assert p["source"] == "snapshot"
    assert "$8,880.00" in p["body"]
    assert p["diverges_from_snapshot"] is False


def test_email_draft_state_read_merges_the_draft_body(tmp_path):
    shell = {"to": "", "cc": "", "subject": "", "body": ""}
    draft = {"body": POST_BODY, "subject": "Quote",
             "to_emails": ["steve@example.com"]}
    db = _seed(tmp_path, SNAP, [
        ("a1", "save_draft", "email",
         {"content": shell, "draft": draft, "review_status": "accepted"},
         "2026-10-08T22:09:35"),
    ])
    p = L.canvas_projection(db, "cv-1")
    assert "$8,984.00" in p["body"]
    assert p["subject"] == "Quote"
    assert p["to"] == "steve@example.com"
    assert p["source"] == "audit+draft"


def test_review_state_semantics_are_exposed_not_flattened(tmp_path):
    db = _seed(tmp_path, SNAP, [
        ("a1", "update", "email",
         {"content": PENDING, "review_status": "pending_review"},
         "2026-10-08T22:09:35"),
    ])
    p = L.canvas_projection(db, "cv-1")
    assert p["review_status"] == "pending_review"
    assert p["diverges_from_snapshot"] is True
    snap = L.canvas_projection(db, "cv-1")["snapshot_text"]
    assert snap != p["text"]


def test_the_runners_preservation_reader_is_the_projection(tmp_path):
    """case1_quote_trials.canvas_content must return the projected text —
    that is what figures_near_label and the manual-cell diff scan."""
    db = _seed(tmp_path, SNAP, [
        ("a1", "update", "email",
         {"content": PENDING, "review_status": "pending_review"},
         "2026-10-08T22:09:35"),
    ])
    assert C.canvas_content(db, "cv-1") == L.canvas_projection(db, "cv-1")["text"]
    scanned = C.figures_near_label(C.canvas_content(db, "cv-1"), "SLE24-16")
    assert "$8,984.00" in scanned and "$8,880.00" not in scanned
    proj = C.canvas_projection(db, "cv-1")
    assert proj["review_status"] == "pending_review"
    assert proj["source"] == "audit"


def test_unknown_canvas_fails_closed(tmp_path):
    db = _seed(tmp_path, SNAP, [
        ("a1", "update", "email", {"content": SNAP}, "2026-10-06T00:55:39"),
    ])
    assert L.canvas_projection(db, "cv-missing")["success"] is False


def test_deleted_canvas_is_reported_not_projected(tmp_path):
    db = _seed(tmp_path, SNAP, [
        ("a1", "update", "email", {"content": SNAP}, "2026-10-06T00:55:39"),
        ("a2", "delete", "email", {}, "2026-10-08T22:09:35"),
    ])
    p = L.canvas_projection(db, "cv-1")
    assert p["success"] is False and p.get("deleted") is True
