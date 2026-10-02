# -*- coding: utf-8 -*-
"""The supersession-churn and duplicate-canvas fixes (2026-10-02).

Two root causes behind the live failures on the quote conversation:

1. TASK CHURN LOSES THE ITEM SET: supersession pops the stored task and
   stashes its context, so when the ask lane stores the replacement via
   merge_pending_task, ``existing`` arrives None and the replacement was
   born with no requested_targets — the read then ran empty (header +
   coverage footer + NO body). merge_pending_task now accepts the
   supersession stash as ``inherit`` and fills only the gaps.

2. SAME-TITLED CANVAS SIBLINGS: two creation paths (chat draft →
   canvas, email compose) each inserted a new Canvas with the identical
   subject (live: two "Quote – …" canvases; edits landed on whichever
   the panel had open). Both paths now dedup: the chat route adopts the
   same-conversation canvas of the same type/title; create_email_canvas
   adopts the chat-created canvas with the same subject instead of
   forking a compose sibling.
"""
from __future__ import annotations

import os

os.environ.setdefault("TESTING", "1")

import pytest

from core.pending_file_task import build_pending_task, merge_pending_task


# ─── supersession-stash inheritance ──────────────────────────────────────


STASH = {
    "requested_targets": ["A-1", "B-2"],
    "resolved_file": {"file_name": "w.xlsx", "resource_id": "res-1"},
    "confirmed_mention": "w.xlsx",
    "disambiguation": {"region": "us"},
}


class TestMergeInheritsFromSupersessionStash:
    def test_replacement_inherits_targets_when_existing_was_popped(self):
        """The live shape: the pop at supersession time leaves
        existing=None — the replacement must still carry the objective's
        item set from the stash."""
        replacement = merge_pending_task(
            None, "cross check what's already confirmed", "w.xlsx",
            inherit=STASH)
        assert replacement["requested_targets"] == ["A-1", "B-2"]
        assert replacement["resolved_file"] == STASH["resolved_file"]
        assert replacement["confirmed_mention"] == "w.xlsx"

    def test_inherit_never_clobbers_the_replacements_own_context(self):
        replacement = merge_pending_task(
            None, "check the other workbook", "other.xlsx",
            disambiguation={"region": "eu"},
            inherit=STASH)
        assert replacement["disambiguation"] == {"region": "eu"}
        # no own mention mismatch case: mention IS a parameter, the
        # confirmed_mention inheritance only fills a gap
        assert replacement["confirmed_mention"] == STASH[
            "confirmed_mention"]

    def test_existing_branch_unchanged_and_outranks_inherit(self):
        existing = build_pending_task(
            "find the prices of these 8 machines: A-1, B-2", "w.xlsx")
        existing["task_id"] = "task-old"
        existing["requested_targets"] = ["A-1", "B-2"]
        merged = merge_pending_task(
            existing, "yes", "w.xlsx", inherit=STASH)
        # merge (confirmation) keeps the ORIGINAL ask and its targets
        assert merged["requested_targets"] == ["A-1", "B-2"]
        assert merged["original_message"] == existing["original_message"]

    def test_replacement_with_existing_still_beats_inherit(self):
        existing = build_pending_task("older ask", "w.xlsx")
        existing["task_id"] = "task-old"
        replacement = merge_pending_task(
            existing, "a newer substantive ask", "w.xlsx", inherit=STASH)
        # the existing-task branch already ran (supersedes stamped), the
        # stash fills nothing that branch covered
        assert replacement["supersedes"]["task_id"] == "task-old"
        assert replacement["resolved_file"] == STASH["resolved_file"]


# ─── email canvas adoption ───────────────────────────────────────────────


@pytest.fixture
def db_session(tmp_path):
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from core.models import Base

    eng = create_engine(f"sqlite:///{tmp_path}/canvas_dedup.db")
    Base.metadata.create_all(bind=eng)
    Session = sessionmaker(bind=eng, expire_on_commit=False)
    with Session() as s:
        yield s


def _seed_chat_canvas(db, canvas_id, name, content, subject_source=True):
    from core.models import Canvas, CanvasAudit

    db.add(Canvas(
        id=canvas_id, tenant_id="default", workspace_id="default",
        created_by="u-1", name=name, canvas_type="email",
        content=content, status="active"))
    db.add(CanvasAudit(
        canvas_id=canvas_id, tenant_id="default", action_type="create",
        canvas_type="email", user_id="u-1",
        details_json=(
            {"source": "chat_to_canvas", "title": name,
             "content": content} if subject_source
            else {"source": "zoho_workdrive", "title": name})))
    db.commit()
    return canvas_id


class TestEmailCanvasAdoptsTheChatCanvas:
    def test_same_subject_compose_adopts_instead_of_forking(self, db_session):
        from core.canvas_email_service import EmailCanvasService
        from core.models import Canvas, CanvasAudit

        seeded = _seed_chat_canvas(
            db_session, "cv-chat", "Quote – Machines",
            {"to": "s@x.test", "cc": "", "subject": "Quote – Machines",
             "body": "<p>Hi Steve</p>"})
        result = EmailCanvasService(db_session).create_email_canvas(
            user_id="u-1", subject="Quote – Machines",
            recipients=["s@x.test"])
        assert result["success"] is True
        assert result["canvas_id"] == seeded
        # no sibling was inserted
        assert db_session.query(Canvas).filter(
            Canvas.name == "Quote – Machines").count() == 1
        # the empty draft did NOT wipe the populated artifact
        row = db_session.get(Canvas, seeded)
        assert "Hi Steve" in str(row.content.get("body") or "")
        # the compose thread state lands on the ADOPTED canvas's trail
        compose_rows = db_session.query(CanvasAudit).filter(
            CanvasAudit.canvas_id == seeded,
            CanvasAudit.action_type == "create").all()
        assert any(
            (r.details_json or {}).get("component_type") == "compose_form"
            for r in compose_rows)

    def test_different_subject_still_creates_a_new_canvas(self, db_session):
        from core.canvas_email_service import EmailCanvasService
        from core.models import Canvas

        _seed_chat_canvas(
            db_session, "cv-chat", "Quote – Machines",
            {"to": "", "cc": "", "subject": "Quote – Machines",
             "body": "<p>x</p>"})
        result = EmailCanvasService(db_session).create_email_canvas(
            user_id="u-1", subject="Quote – Other gear",
            recipients=["s@x.test"])
        assert result["success"] is True
        assert result["canvas_id"] != "cv-chat"
        assert db_session.query(Canvas).filter(
            Canvas.name == "Quote – Other gear").count() == 1

    def test_no_adoption_when_the_existing_canvas_is_not_chat_created(
            self, db_session):
        from core.canvas_email_service import EmailCanvasService
        from core.models import Canvas

        _seed_chat_canvas(
            db_session, "cv-imp", "Quote – Machines",
            {"to": "", "cc": "", "subject": "Quote – Machines",
             "body": "<p>x</p>"}, subject_source=False)
        result = EmailCanvasService(db_session).create_email_canvas(
            user_id="u-1", subject="Quote – Machines",
            recipients=["s@x.test"])
        assert result["success"] is True
        assert result["canvas_id"] != "cv-imp"
        assert db_session.query(Canvas).count() == 2


# ─── chat-route same-conversation dedup ──────────────────────────────────


class _FakeRequest:
    def __init__(self, body):
        self._body = body

    async def json(self):
        return self._body


class _FakeUser:
    id = "u-1"
    tenant_id = "default"
    workspaces: list = []


async def _call_chat_draft_to_canvas(db, body):
    from integrations.chat_routes import chat_draft_to_canvas

    return await chat_draft_to_canvas(
        request=_FakeRequest(body), current_user=_FakeUser(), db=db)


class TestChatRouteSameConversationDedup:
    BODY = {"content": "Rebuilt quote body", "title": "Quote – Machines",
            "session_id": "s-1", "canvas_type": "document"}

    def _seed(self, db, session_id):
        from core.models import Canvas, CanvasAudit

        db.add(Canvas(
            id="cv-doc", tenant_id="default", created_by="u-1",
            name="Quote – Machines", canvas_type="document",
            content={"content": "old draft"}, status="active"))
        db.add(CanvasAudit(
            canvas_id="cv-doc", tenant_id="default", action_type="create",
            canvas_type="document", user_id="u-1", session_id=session_id,
            details_json={"source": "chat_to_canvas",
                          "title": "Quote – Machines"}))
        db.commit()

    @pytest.mark.asyncio
    async def test_recreate_updates_the_existing_artifact(
            self, db_session):
        self._seed(db_session, "s-1")
        result = await _call_chat_draft_to_canvas(db_session, self.BODY)
        from core.models import Canvas, CanvasAudit

        assert result["success"] is True
        assert result["canvas_id"] == "cv-doc"
        assert db_session.query(Canvas).filter(
            Canvas.name == "Quote – Machines").count() == 1
        row = db_session.get(Canvas, "cv-doc")
        assert row.content == {"content": "Rebuilt quote body"}
        updates = db_session.query(CanvasAudit).filter(
            CanvasAudit.canvas_id == "cv-doc",
            CanvasAudit.action_type == "update").all()
        assert any(
            (u.details_json or {}).get("dedup") ==
            "adopted_same_conversation_canvas" for u in updates)

    @pytest.mark.asyncio
    async def test_other_conversation_creates_its_own(self, db_session):
        self._seed(db_session, "s-other")
        result = await _call_chat_draft_to_canvas(db_session, self.BODY)
        from core.models import Canvas

        assert result["success"] is True
        assert result["canvas_id"] != "cv-doc"
        assert db_session.query(Canvas).filter(
            Canvas.name == "Quote – Machines").count() == 2
