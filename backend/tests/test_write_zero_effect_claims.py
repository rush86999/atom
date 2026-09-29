"""Every user-facing "nothing was changed" must be a VERIFIED claim.

THE RULE
--------
A refusal is not a zero effect. Three separate counters used to be read as
proof that a canvas was untouched, and none of them is:

  * an exhausted RETRY/BUDGET count — says "we stopped trying";
  * a store REFUSAL — `update_canvas_content` / `restore_canvas_version`
    report `success: False` for a failure that happened AFTER their own commit
    (refresh, the context manager's exit commit, the broadcast), which is a
    durable write wearing a refusal's clothes;
  * a REVISION CONFLICT — the canvas really did change, just not by us.

So the store now states, on every return, whether its append was attempted
(`write_outcome`), the editor maps anything but `not_attempted` onto
`write_uncertain`, and `describe_apply_failure` answers a reason only with
"nothing was changed" when the refusal is on the pre-write allow-list. The
DEFAULT direction is uncertain: a reason nobody audited cannot silently
inherit a confident zero-effect claim.

`async_turn_continuation`'s own two zero-effect sites are gated separately by
`_verified_zero_effect` (two independent durable-store observations plus a
content-hash cross-check) and are covered by `test_zero_effect_claim.py`. This
file covers the OTHER half of the same rule: the synchronous edit path.
"""
from __future__ import annotations

import os
import sys
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("TESTING", "1")

from core.chat_canvas_editor import (  # noqa: E402
    CanvasEditPlan,
    VERIFIED_PRE_WRITE_REFUSALS,
    _verified_zero_effect_refusal,
    apply_canvas_edit,
    describe_apply_failure,
)
from core.models_registration import Base  # noqa: E402


# ---------------------------------------------------------------------------
# 1. THE STORE: a refusal is only a zero effect if the append was never tried
# ---------------------------------------------------------------------------

class _FlakySession(Session):
    """A real session with one method that can be made to fail.

    `refresh` is the cheapest honest way to model a failure that happens AFTER
    the commit: the row is already durable, so the store must not report a
    verified zero effect. `commit` is the one that models a commit whose
    outcome cannot be established at all (a lost connection after the server
    committed is the classic case).
    """

    fail_refresh = False
    fail_commit = False

    def refresh(self, *args, **kwargs):
        if self.fail_refresh:
            raise RuntimeError("refresh failed after the commit")
        return super().refresh(*args, **kwargs)

    def commit(self, *args, **kwargs):
        if self.fail_commit:
            raise RuntimeError("commit outcome unknown")
        return super().commit(*args, **kwargs)


@pytest.fixture
def store_db():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False},
                           poolclass=StaticPool)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, class_=_FlakySession, expire_on_commit=False)
    from core.models import Canvas, CanvasAudit

    session = factory()
    try:
        session.add(Canvas(id="cv-1", name="Draft", canvas_type="email",
                           created_by="u1", tenant_id="t"))
        session.add(CanvasAudit(
            canvas_id="cv-1", tenant_id="t", action_type="create",
            canvas_type="email", user_id="u1",
            details_json={"content": {"body": "old"}},
        ))
        session.commit()
    finally:
        session.close()
    _FlakySession.fail_refresh = False
    _FlakySession.fail_commit = False
    yield factory
    _FlakySession.fail_refresh = False
    _FlakySession.fail_commit = False
    engine.dispose()


def _use_store(factory):
    from contextlib import contextmanager

    import core.database as database_module

    @contextmanager
    def _session():
        db = factory()
        try:
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    return patch.object(database_module, "get_db_session", _session)


@pytest.mark.asyncio
async def test_a_successful_write_reports_committed(store_db):
    from tools.canvas_crud_tool import WRITE_COMMITTED, update_canvas_content

    with _use_store(store_db):
        result = await update_canvas_content("u1", "cv-1", {"body": "new"})
    assert result["success"] is True
    assert result["write_outcome"] == WRITE_COMMITTED


@pytest.mark.asyncio
async def test_a_refusal_before_the_append_reports_not_attempted(store_db):
    """The IDOR / missing-canvas refusals are VERIFIED zero effects."""
    from tools.canvas_crud_tool import WRITE_NOT_ATTEMPTED, update_canvas_content

    with _use_store(store_db):
        result = await update_canvas_content("someone-else", "cv-1", {"body": "new"})
    assert result["success"] is False
    assert result["write_outcome"] == WRITE_NOT_ATTEMPTED


@pytest.mark.asyncio
async def test_a_revision_conflict_reports_not_attempted(store_db):
    from tools.canvas_crud_tool import WRITE_NOT_ATTEMPTED, update_canvas_content

    with _use_store(store_db):
        result = await update_canvas_content(
            "u1", "cv-1", {"body": "new"},
            expected_prior_audit_id="not-the-latest-row")
    assert result["success"] is False
    assert result.get("conflict") is True
    assert result["write_outcome"] == WRITE_NOT_ATTEMPTED


@pytest.mark.asyncio
async def test_a_failure_after_the_commit_is_not_reported_as_a_refusal(store_db):
    """THE DEFECT, at its source.

    The write is durable and the store still answers `success: False` — a
    post-commit failure. If it also answered "not attempted", the caller would
    tell a user their canvas was untouched while their edit is sitting in it.
    """
    from tools.canvas_crud_tool import WRITE_COMMITTED, update_canvas_content
    from core.models import CanvasAudit

    _FlakySession.fail_refresh = True
    try:
        with _use_store(store_db):
            result = await update_canvas_content("u1", "cv-1", {"body": "new"})
    finally:
        _FlakySession.fail_refresh = False
    assert result["success"] is False
    assert result["write_outcome"] == WRITE_COMMITTED
    # ... and the row really is there, so the claim of "nothing changed" would
    # have been false.
    session = store_db()
    try:
        rows = [r for r in session.query(CanvasAudit)
                .filter(CanvasAudit.canvas_id == "cv-1").all()
                if r.action_type == "update"]
        assert len(rows) == 1, "the append did not land, so this test proves nothing"
        assert (rows[0].details_json or {}).get("content", {}).get("body") == "new"
    finally:
        session.close()


@pytest.mark.asyncio
async def test_a_commit_that_raises_is_unknown_not_not_attempted(store_db):
    """A commit whose outcome cannot be established is the weakest verdict,
    and it must not collapse into 'nothing changed' either."""
    from tools.canvas_crud_tool import WRITE_UNKNOWN, update_canvas_content

    _FlakySession.fail_commit = True
    try:
        with _use_store(store_db):
            result = await update_canvas_content("u1", "cv-1", {"body": "new"})
    finally:
        _FlakySession.fail_commit = False
    assert result["success"] is False
    assert result["write_outcome"] == WRITE_UNKNOWN


@pytest.mark.asyncio
async def test_a_restore_that_refused_before_appending_is_not_attempted(store_db):
    from tools.canvas_crud_tool import WRITE_NOT_ATTEMPTED, restore_canvas_version

    with _use_store(store_db):
        result = await restore_canvas_version("u1", "cv-1", "no-such-version")
    assert result["success"] is False
    assert result["write_outcome"] == WRITE_NOT_ATTEMPTED


# ---------------------------------------------------------------------------
# 2. THE EDITOR: the store's verdict becomes the reason
# ---------------------------------------------------------------------------

def _plan():
    return CanvasEditPlan(wants_edit=True, edit_mode="replace",
                          updated_content_json='{"body": "new"}', reply="ok")


async def _apply_with_store_result(store_result, **canvas_overrides):
    canvas = {"canvas_id": "cv-1", "canvas_type": "email", "content": {"body": "old"}}
    canvas.update(canvas_overrides)
    with patch("tools.canvas_crud_tool.update_canvas_content",
               new=AsyncMock(return_value=store_result)):
        return await apply_canvas_edit(_plan(), "u1", canvas, return_reason=True)


@pytest.mark.asyncio
async def test_a_pre_write_store_refusal_still_reports_a_verified_zero_effect():
    _result, reason = await _apply_with_store_result(
        {"success": False, "error": "Canvas cv-1 not found",
         "write_outcome": "not_attempted"})
    assert reason == "store_rejected: Canvas cv-1 not found"
    assert "Nothing was changed" in describe_apply_failure(reason, "email")


@pytest.mark.asyncio
@pytest.mark.parametrize("write_outcome", ["committed", "unknown", None, ""])
async def test_a_store_failure_that_may_have_written_is_never_a_zero_effect(
    write_outcome
):
    """Every non-`not_attempted` verdict — including a store that answers
    nothing at all — has to lose its zero-effect claim."""
    store_result = {"success": False, "error": "refresh failed after the commit"}
    if write_outcome is not None:
        store_result["write_outcome"] = write_outcome
    _result, reason = await _apply_with_store_result(store_result)
    assert reason == "write_uncertain: refresh failed after the commit"
    said = describe_apply_failure(reason, "email")
    assert "Nothing was changed" not in said
    assert any(marker in said for marker in DOUBT_MARKERS), said


@pytest.mark.asyncio
async def test_an_exception_escaping_the_store_call_is_never_a_zero_effect():
    with patch("tools.canvas_crud_tool.update_canvas_content",
               new=AsyncMock(side_effect=RuntimeError("connection reset"))):
        _result, reason = await apply_canvas_edit(
            _plan(), "u1",
            {"canvas_id": "cv-1", "canvas_type": "email", "content": {"body": "old"}},
            return_reason=True,
        )
    assert reason == "write_uncertain: connection reset"
    said = describe_apply_failure(reason, "email")
    assert "Nothing was changed" not in said
    assert any(marker in said for marker in DOUBT_MARKERS), said


# ---------------------------------------------------------------------------
# 3. THE WORDS: which reasons may claim a zero effect, and which may not
# ---------------------------------------------------------------------------

#: Reasons `apply_canvas_edit` returns after deciding BEFORE the store call, or
#: which the store itself verified as `not_attempted`. `claims_zero_effect` says
#: whether that reason's own wording asserts the canvas is unchanged — some
#: backed refusals make a different (equally supported) statement instead, and
#: inventing a zero-effect sentence for those would be a new unbacked claim.
BACKED_REASONS = [
    ("not_an_edit", False),
    ("no_ready_evidence_change", False),
    ("evidence_contract_forbids_restore", False),
    ("file_backed", False),
    ("no_change", False),  # "nothing needed changing" — a no-op, not a refusal
    ("not_valid_json", True),
    ("no_content", True),
    ("ops_no_longer_match", True),
    ("merge_failed", True),
    ("restore_missing_version", True),
    ("version_not_found", True),
    ("store_rejected: Canvas cv-1 not found", True),
    ("dead_link: https://dead.ca/x", True),  # "I left your draft unchanged"
    ("postcondition_missing:ent-1", True),
    ("scope_row_count", True),
    ("scope_missing_price", True),
    ("footer_missing_contact", True),
]

#: Reasons where the canvas may or may not have moved. None of these may deny a
#: change, and each has to say so.
UNCERTAIN_REASONS = [
    "write_uncertain: refresh failed after the commit",
    "store_error: connection reset",
    # An unaudited reason must not inherit the claim by omission — this is the
    # case that a future refusal path would hit.
    "some_refusal_nobody_audited",
    "",
    None,
]

#: The wording that carries the doubt. Anything reachable by an unverified
#: outcome has to contain one of them.
DOUBT_MARKERS = (
    "can't tell you whether",
    "couldn't confirm whether",
    "doesn't tell me whether",
)


@pytest.mark.parametrize("reason,claims_zero_effect", BACKED_REASONS)
def test_a_pre_write_refusal_is_answered_definitively(reason, claims_zero_effect):
    assert _verified_zero_effect_refusal(reason) is True, reason
    said = describe_apply_failure(reason, "email")
    assert said.strip(), reason
    assert not any(marker in said for marker in DOUBT_MARKERS), (
        f"{reason} is a verified no-write; doubt about it is noise")
    if claims_zero_effect:
        assert "nothing was changed" in said.lower() or \
            "nothing was written" in said.lower() or \
            "unchanged" in said.lower(), (reason, said)


@pytest.mark.parametrize("reason", UNCERTAIN_REASONS)
def test_an_unverified_outcome_never_denies_a_change(reason):
    assert _verified_zero_effect_refusal(reason) is False, reason
    said = describe_apply_failure(reason, "email")
    assert "nothing was changed" not in said.lower(), (reason, said)
    assert any(marker in said for marker in DOUBT_MARKERS), (reason, said)


def test_the_conflict_branch_is_definitive_about_who_moved_the_canvas():
    """A revision conflict is not a zero effect and not a mystery either: the
    canvas DID change, by someone else, and the user is about to look at it.
    Wording that hedges here would be as wrong as denying it."""
    said = describe_apply_failure("conflict: canvas changed during the edit", "email")
    assert "Nothing was changed" not in said
    assert "changed while I was working" in said
    assert "overwrite" in said
    assert "Nothing of mine was written" in said
    assert not any(marker in said for marker in DOUBT_MARKERS), said


def test_the_conflict_branch_says_the_canvas_actually_moved():
    """A revision conflict is not a zero effect: the canvas DID change, by
    someone else, and the user is about to look at it."""
    said = describe_apply_failure("conflict: canvas changed during the edit", "email")
    assert "Nothing was changed" not in said
    assert "changed while I was working" in said
    assert "overwrite" in said


def test_the_allow_list_cannot_silently_grow_to_cover_the_store():
    """The store-facing reasons are absent from the allow-list on purpose, and
    that is the property worth pinning: a later edit that 'helpfully' adds
    `store_rejected` semantics for an unknown outcome would have to delete this
    assertion first."""
    for reason in ("write_uncertain", "store_error", "conflict"):
        assert reason not in VERIFIED_PRE_WRITE_REFUSALS, (
            f"{reason} is not a verified zero effect and must not be on the "
            "allow-list")


# ---------------------------------------------------------------------------
# 4. THE PLANNER-UNAVAILABLE SENTENCE: what keeps it true
# ---------------------------------------------------------------------------
# `chat_orchestrator` answers a turn whose edit PLANNER was unavailable with
# "I couldn't complete this request. Nothing was changed." Nothing on that leg
# wrote, so the sentence is backed — but only because the background
# continuation that WOULD still be able to write takes a different branch that
# returns first, and says the edit is still running. If those two branches ever
# overlapped, a turn would deny a change its own background worker was about to
# make. That mutual exclusivity is the whole basis of the claim, so it is
# pinned here rather than assumed.

async def _planner_unavailable_turn(message, session_id, reply_text):
    from unittest.mock import MagicMock

    from integrations import chat_orchestrator as chat

    orchestrator = chat.ChatOrchestrator()
    canvas = {"canvas_id": "cv1", "canvas_type": "email",
              "content": {"subject": "Draft", "body": "Unchanged"}}
    forks = []

    async def planner_down(*a, **k):
        state = k.get("shared_tool_state")
        if state is not None:
            state["canvas_planning_unavailable"] = True
        return None

    with (
        patch.object(orchestrator, "_get_or_create_session",
                     return_value={"id": session_id, "history": []}),
        patch.object(orchestrator, "_resolve_canvas_ctx",
                     new=AsyncMock(return_value=canvas)),
        patch.object(orchestrator, "_start_chat_execution", return_value="e1"),
        patch.object(orchestrator, "_record_chat_step", new=AsyncMock()),
        patch.object(orchestrator, "_emit_agent_status", new=AsyncMock()),
        patch.object(orchestrator, "_finish_chat_execution"),
        patch.object(orchestrator, "_update_session"),
        patch.object(orchestrator, "_try_canvas_edit", side_effect=planner_down),
        patch.object(orchestrator, "_try_canvas_action", new=AsyncMock()),
        patch.object(orchestrator, "_get_qwen_response",
                     new=AsyncMock(return_value=reply_text)),
        patch("core.chat_tool_planner.plan_tool_use",
              new=AsyncMock(return_value=None)),
        patch("core.chat_tool_planner._provenance_menu",
              new=AsyncMock(return_value="")),
        patch("core.async_turn_continuation.fork_canvas_edit_continuation",
              side_effect=lambda *a, **k: forks.append(k) or "cont-1"),
    ):
        return await orchestrator.process_chat_message(
            "u1", message, session_id, context={"canvas_id": "cv1"}), forks


@pytest.mark.asyncio
async def test_an_edit_shaped_planner_failure_never_denies_a_change():
    """The background worker is still going to try this edit, so the reply
    cannot say nothing was changed."""
    result, forks = await _planner_unavailable_turn(
        "rebuild the draft with the quotes", "sess-zero-a",
        {"content": "ok", "model": "m", "provider": "p"})
    assert len(forks) == 1, "an edit-shaped planner failure must fork the retry"
    said = (result.get("message") or "").lower()
    assert "nothing was changed" not in said, result.get("message")
    assert "background" in said, result.get("message")


@pytest.mark.asyncio
async def test_a_non_edit_turn_may_say_nothing_was_changed_because_nothing_started():
    """The same sentence on the branch that can reach it, with the condition
    that makes it true asserted rather than assumed: no fork, so nothing is in
    flight that could still change this canvas after the reply."""
    result, forks = await _planner_unavailable_turn(
        "what does the draft say about pricing", "sess-zero-b", None)
    assert forks == [], (
        "if a background edit were in flight, this reply could not deny a "
        "change")
    assert "Nothing was changed" in (result.get("message") or ""), result
