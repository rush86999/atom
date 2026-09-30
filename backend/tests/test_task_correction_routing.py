# -*- coding: utf-8 -*-
"""Task correction (item replacement) — the turn must reach the file lane.

Live defect this file pins (2026-09-27). "Replace U-22 with U-38" was
answered "I've added 'Replace U-22 with U-38' to your Tasks." — a real task
row manufactured from a correction to a spreadsheet lookup, and the previous
list shown back. Three separate causes, each pinned here:

1. The reply leg's evidence-bound narration guard read
   ``_pfr_structured_for_turn``, a local of ``process_chat_message``, from
   inside ``_get_qwen_response``. Every turn that produced a structured
   workbook record raised ``NameError`` there; the enclosing ``except``
   swallowed it, the reply was discarded, and the turn fell through to
   legacy feature routing — which is what handed it to the TASKS handler.
   The general form of that bug class is pinned in
   ``test_reply_leg_name_safety.py``; here only the guard's chosen record is.

2. A COMPLETED ask-turn direct read stored no pending file task, so a
   delivered read had no durable record of what it was a read OF. Every
   continuation (a set edit, a re-search, a reload) resolves through
   ``matching_pending_task``, so the resume lane was never entered.
   Pinned by ``test_completed_ask_stores_a_delivered_task``.

3. An entity-set edit on a file objective was offered to
   ``FeatureType.TASKS``. Pinned by ``TestTaskLaneIsNotOfferedForASetEdit``.

Fail-closed is asserted throughout: an ordinary "replace the logo in the
draft" and a genuine "replace my Q3 task with Q4" must both keep reaching
the task lane.
"""
from __future__ import annotations

import ast
import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("TESTING", "1")

import integrations.chat_orchestrator as chat  # noqa: E402
from core.pending_file_task import (  # noqa: E402
    FILE_TASK_SESSION_KEY,
    build_pending_task,
    entity_set_edit,
    mark_task_delivered,
    mark_task_retrieved,
    matching_pending_task,
)

BASE_ASK = (
    "find the prices of these 8 machines in Consolidated Price List "
    "2019.xlsx: No. 381, U-22, No. 622, TK Manual Flanger, SLE24-16, "
    "TK 1624, TK Multi Wheel Gang Slitter and GSL48-16")
MENTION = "consolidated price list 2019.xlsx"
REPLACE_TURN = "Replace U-22 with U-38"


def _file_objective_session() -> dict:
    return {
        "id": "s1",
        "history": [],
        FILE_TASK_SESSION_KEY: mark_task_delivered(
            mark_task_retrieved(
                build_pending_task(BASE_ASK, MENTION),
                {"file_id": "r1", "file_name": "Consolidated Price List 2019.xlsx"},
            )
        ),
    }


# ---------------------------------------------------------------------------
# The gate: an entity-set edit on a file objective
# ---------------------------------------------------------------------------

class TestFileObjectiveTurn:
    def test_set_edit_on_a_stored_objective_is_a_file_objective_turn(self):
        assert chat._is_file_objective_turn(
            REPLACE_TURN, _file_objective_session()) is True

    @pytest.mark.parametrize("turn", [
        "drop U-22",
        "also add U-38",
        "swap U-22 for U-38",
        "replace U-22 with U-38 and GSL48-16",
    ])
    def test_every_set_edit_verb_shape_counts(self, turn):
        assert chat._is_file_objective_turn(
            turn, _file_objective_session()) is True

    def test_a_resolved_file_identity_alone_is_enough(self):
        """The durable carrier can be reached through any one of the three
        session keys; requiring the pending task alone would miss a session
        whose task row was never written."""
        assert chat._is_file_objective_turn(
            REPLACE_TURN, {"_resolved_file_identity": {"file_id": "r1"}}) is True
        assert chat._is_file_objective_turn(
            REPLACE_TURN, {"_pending_file_result": {"status": "delivered"}}) is True

    # -- fail-closed: neither condition alone is enough ----------------------

    @pytest.mark.parametrize("turn", [
        "replace the logo in the draft",
        "replace the price with the cost",
        "send me the price list",
        "edit the canvas quote",
        "what is the capital of France?",
    ])
    def test_ordinary_sentences_are_not_set_edits(self, turn):
        assert chat._is_file_objective_turn(
            turn, _file_objective_session()) is False

    def test_a_set_edit_with_no_file_objective_is_not_one(self):
        """No item set exists to edit, so the turn is whatever the NLU said
        it was — the gate must not silently swallow it."""
        assert chat._is_file_objective_turn(REPLACE_TURN, {}) is False
        assert chat._is_file_objective_turn(REPLACE_TURN, None) is False
        assert chat._is_file_objective_turn(REPLACE_TURN, {"id": "s1"}) is False

    def test_a_non_dict_session_key_does_not_count(self):
        assert chat._is_file_objective_turn(
            REPLACE_TURN, {FILE_TASK_SESSION_KEY: "not a task"}) is False


# ---------------------------------------------------------------------------
# Routing: the task lane is not offered a correction to a lookup
# ---------------------------------------------------------------------------

def _orch_with_handlers():
    orch = chat.ChatOrchestrator()
    orch.ai_engines = {}
    calls: list = []

    async def _tasks(message, intent_analysis, session, context):
        calls.append(("tasks", message))
        return {"success": True, "message": "I've added it to your Tasks."}

    async def _automation(message, intent_analysis, session, context):
        calls.append(("automation", message))
        return {"success": False, "error": "nothing to do"}

    async def _agent(*a, **kw):
        calls.append(("agent", kw.get("goal")))
        return {"id": "task-1", "status": "queued"}

    orch.feature_handlers = {
        chat.FeatureType.TASKS: _tasks,
        chat.FeatureType.AUTOMATION: _automation,
    }
    return orch, calls, _agent


class TestTaskLaneIsNotOfferedForASetEdit:
    @pytest.mark.asyncio
    async def test_a_set_edit_never_creates_a_task_row(self):
        orch, calls, _agent = _orch_with_handlers()
        with patch.object(chat, "agent_service", MagicMock(
                execute_task=AsyncMock(return_value={"id": "t", "status": "q"}))):
            responses = await orch._route_to_features(
                REPLACE_TURN,
                {"primary_intent": chat.ChatIntent.TASK_MANAGEMENT},
                _file_objective_session(),
                {},
            )
        assert chat.FeatureType.TASKS not in responses, (
            "the correction must not be answered by creating a task")
        assert all(name != "tasks" for name, _ in calls)

    @pytest.mark.asyncio
    async def test_a_genuine_task_request_still_creates_one(self):
        orch, calls, _agent = _orch_with_handlers()
        await orch._route_to_features(
            "remind me to call the vendor tomorrow",
            {"primary_intent": chat.ChatIntent.TASK_MANAGEMENT},
            _file_objective_session(),
            {},
        )
        assert ("tasks", "remind me to call the vendor tomorrow") in calls

    @pytest.mark.asyncio
    async def test_replacing_a_task_by_name_still_reaches_the_task_lane(self):
        """'replace' is a task verb too. A named TASK being replaced is not
        an entity-set edit and must not be diverted."""
        orch, calls, _agent = _orch_with_handlers()
        await orch._route_to_features(
            "replace the task 'call the vendor' with 'email the vendor'",
            {"primary_intent": chat.ChatIntent.TASK_MANAGEMENT},
            _file_objective_session(),
            {},
        )
        assert any(name == "tasks" for name, _ in calls), (
            "a task-to-task replacement is still task management")

    @pytest.mark.asyncio
    async def test_a_set_edit_with_no_file_objective_still_reaches_tasks(self):
        orch, calls, _agent = _orch_with_handlers()
        await orch._route_to_features(
            REPLACE_TURN,
            {"primary_intent": chat.ChatIntent.TASK_MANAGEMENT},
            {"id": "s-empty", "history": []},
            {},
        )
        assert any(name == "tasks" for name, _ in calls)


# ---------------------------------------------------------------------------
# The durable carrier: a completed ask stores a delivered task
# ---------------------------------------------------------------------------

def _orch():
    orch = chat.ChatOrchestrator()
    orch.ai_engines = {}
    llm = MagicMock()
    llm.generate_completion = AsyncMock(return_value={
        "success": True, "content": "reply", "model": "m", "provider": "p",
    })
    orch.llm_service = llm
    return orch


_COMPLETE_READ = {
    "ok": True,
    "block": (
        "Workbook read: Consolidated Price List 2019.xlsx\n"
        "| U-22 | FOUND | Sheet1!A2 R2 [basis=List; currency=unspecified] |"
    ),
    "rendered_answer": (
        "Workbook read: Consolidated Price List 2019.xlsx\n"
        "| U-22 | FOUND | Sheet1!A2 R2 [basis=List; currency=unspecified] |"
    ),
    "identity": {
        "file_id": "r1",
        "resource_id": "r1",
        "file_name": "Consolidated Price List 2019.xlsx",
        "identity_verified": True,
        "coverage_complete": True,
    },
    "meta": {"completed": True, "identity_verified": True,
             "coverage_complete": True},
    "retrieval_complete": True,
}


@pytest.mark.asyncio
async def test_completed_ask_stores_a_delivered_task():
    """A COMPLETED ask-turn direct read must leave a durable record of the
    objective. Before this, only an INCOMPLETE read stored a task, so a
    delivered lookup had nothing for a later set edit to resume and the turn
    fell through to legacy feature routing."""
    orch = _orch()
    session = {"id": "s-ask", "history": []}
    with (
        patch.object(orch, "_get_or_create_session", return_value=session),
        patch.object(orch, "_start_chat_execution", return_value="exec-ask"),
        patch.object(orch, "_update_session"),
        patch.object(orch, "_emit_agent_status", new=AsyncMock()),
        patch.object(orch, "_finish_chat_execution"),
        patch.object(orch, "_direct_confirmed_file_read", new=AsyncMock(
            return_value=_COMPLETE_READ)),
        patch("core.chat_tool_planner.plan_tool_use", new=AsyncMock(
            side_effect=AssertionError("planner must not run"))),
    ):
        response = await orch.process_chat_message(
            "u1", BASE_ASK, session_id="s-ask", context={})

    assert response["success"] is True
    stored = session.get(FILE_TASK_SESSION_KEY)
    assert stored, (
        "a completed read must still record the objective it answered")
    assert stored["status"] == "delivered", (
        "the answer reached the user, so the objective is terminal — a bare "
        "'yes' must not resurrect it (the delivery path owns that)")
    assert stored["original_message"] == BASE_ASK
    assert stored["mention"] == MENTION
    assert (stored.get("resolved_file") or {}).get("file_id") == "r1", (
        "a later re-read must execute against the same resource, not a "
        "fresh resolution")


@pytest.mark.asyncio
async def test_the_stored_task_is_resumable_by_a_set_edit_but_not_by_a_bare_yes():
    """The whole point of storing it: `matching_pending_task` treats a
    delivered task as eligible for a set edit (a fresh attempt is required —
    the delivered evidence cannot answer a different question) and NOT for a
    bare approval."""
    orch = _orch()
    session = {"id": "s-ask", "history": []}
    with (
        patch.object(orch, "_get_or_create_session", return_value=session),
        patch.object(orch, "_start_chat_execution", return_value="exec-ask"),
        patch.object(orch, "_update_session"),
        patch.object(orch, "_emit_agent_status", new=AsyncMock()),
        patch.object(orch, "_finish_chat_execution"),
        patch.object(orch, "_direct_confirmed_file_read", new=AsyncMock(
            return_value=_COMPLETE_READ)),
        patch("core.chat_tool_planner.plan_tool_use", new=AsyncMock(
            side_effect=AssertionError("planner must not run"))),
    ):
        await orch.process_chat_message(
            "u1", BASE_ASK, session_id="s-ask", context={})

    stored = session[FILE_TASK_SESSION_KEY]
    assert matching_pending_task(stored, REPLACE_TURN, []) is not None, (
        "the set edit must reach the resume lane, or the previous list is "
        "what the user sees again")
    assert matching_pending_task(stored, "yes", []) is None
    assert matching_pending_task(stored, "that filename is correct", []) is None
    assert matching_pending_task(stored, "show me something else entirely", []) is None
    # And the edit itself is recognised, with the outgoing item replaced in
    # place so the rest of the order survives.
    edit = entity_set_edit(REPLACE_TURN)
    assert edit["operation"] == "replace"
    assert edit["removed"] == ["U-22"]
    assert edit["added"] == ["U-38"]


# ---------------------------------------------------------------------------
# A revision that cannot be persisted must not be half-applied
# ---------------------------------------------------------------------------

class TestRevisionPersistenceFailureIsFailClosed:
    """The revision must be durable BEFORE the read it authorises.

    The handler used to log "objective revision failed — read blocked", clear
    the local `_objective_edit`, and fall through. `_direct_task` still carried
    the REVISED targets, so the read ran anyway: the answer was computed from
    the new item set while the durable task still held the old one. That is
    the durable/output disagreement this whole path exists to prevent, reached
    by a different route — and a comment claiming fail-closed behaviour is not
    evidence of it.

    So this injects the failure and requires the two things that actually
    matter: no retrieval, and no fallback into a mutating task lane.
    """

    @staticmethod
    def _session():
        return {"id": "s-rev-fail", "history": [],
                FILE_TASK_SESSION_KEY: mark_task_delivered(
                    mark_task_retrieved(
                        build_pending_task(BASE_ASK, MENTION),
                        {"file_id": "r1",
                         "file_name": "Consolidated Price List 2019.xlsx"},
                    )
                )}

    @pytest.mark.asyncio
    async def test_no_read_runs_and_no_task_is_created(self, monkeypatch):
        import integrations.chat_orchestrator as chat

        monkeypatch.setenv("ATOM_TASK_LIFECYCLE_ENABLED", "1")
        orch = _orch()
        session = self._session()
        real_for = chat._task_lifecycle_for

        class _FailingRevision:
            """A lifecycle whose revise_objective cannot be persisted."""

            def __init__(self, inner):
                self._inner = inner

            def get_task(self, run_id):
                return self._inner.get_task(run_id)

            def apply_transition(self, run_id, transition, *a, **kw):
                if transition.get("kind") == "revise_objective":
                    raise RuntimeError("injected revision persistence failure")
                return self._inner.apply_transition(run_id, transition, *a, **kw)

            def __getattr__(self, name):
                return getattr(self._inner, name)

        def _for(tenant_id, workspace_id):
            entry = real_for(tenant_id, workspace_id)
            return _FailingRevision(entry) if entry is not None else None

        monkeypatch.setattr(chat, "_task_lifecycle_for", staticmethod(_for))

        read = AsyncMock(return_value=_COMPLETE_READ)
        routed = AsyncMock(return_value={})
        with (
            patch.object(orch, "_get_or_create_session", return_value=session),
            patch.object(orch, "_start_chat_execution", return_value="exec-rf"),
            patch.object(orch, "_update_session"),
            patch.object(orch, "_emit_agent_status", new=AsyncMock()),
            patch.object(orch, "_finish_chat_execution"),
            patch.object(orch, "_direct_confirmed_file_read", read),
            patch.object(orch, "_route_to_features", routed),
        ):
            response = await orch.process_chat_message(
                "u1", REPLACE_TURN, session_id="s-rev-fail", context={})

        read.assert_not_awaited(), (
            "the read ran against a revision that was never persisted")
        routed.assert_not_awaited(), (
            "a recognised correction fell through to feature routing, which is "
            "how it reached the task-creation lane and answered 'I've added "
            "... to your Tasks'")
        assert response["success"] is False
        assert response["data"]["blocked_reason"] == (
            "objective_revision_not_recorded")
        assert "did not run" in response["message"]
        # The durable objective is untouched: no half-applied correction.
        stored = session[FILE_TASK_SESSION_KEY]
        assert "U-22" in str(stored.get("requested_targets") or
                             stored.get("original_message")), (
            "the outgoing item must still be part of the objective when the "
            "correction could not be recorded")


class TestNarrationGuardJudgesThisTurnsRecord:
    """The guard must read the record THIS turn produced. The session's
    persisted copy is the PREVIOUS turn's answer, so validating against it
    would bless exactly the stale list the guard exists to reject.

    The scope half of this defect — a name bound in one method and read in
    another — is pinned generally in ``test_reply_leg_name_safety.py``, which
    already guards that bug class.
    """

    def test_the_guard_reads_the_turn_local_not_the_persisted_copy(self):
        reply = next(
            n for n in ast.walk(ast.parse(open(chat.__file__).read()))
            if isinstance(n, ast.AsyncFunctionDef)
            and n.name == "_get_qwen_response"
        )
        loaded = {
            n.id for n in ast.walk(reply)
            if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load)
        }
        assert "_pfr_structured_for_turn" not in loaded
        assert "_turn_structured_record" in loaded


# ---------------------------------------------------------------------------
# The correction runner's own evidence helpers
# ---------------------------------------------------------------------------

def _runner():
    import importlib.util
    path = Path(__file__).resolve().parents[1] / (
        "scripts/orchestration_acceptance/task_correction_acceptance.py")
    spec = importlib.util.spec_from_file_location("tca_under_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TestHeadlineValues:
    """The value the answer states per item, read off the rendered line.

    The items legitimately contain hyphens ("U-22", "SLE24-16", "GSL48-16"),
    so a separator-shaped regex splits "U-22" into item "U" and value "22" --
    and a verifier that then reports "22" fails a correct answer, or accepts
    "22" as a price because some row happens to contain it.
    """

    ANSWER = (
        "Results from the saved copy of Consolidated Price List 2019.xlsx:\n"
        "\n"
        "- **No. 381** - several rows match (RoperWhitney!R88 ...)\n"
        "- **U-22** - 1,777 (LINMAC!R26, identity A26, column C26 'List "
        "Price'; also M26 'List Price_2' 1,777)\n"
        "- **TK Multi Wheel Gang Slitter** (matched via 'Gang Slitter') - "
        "several rows match (Tennsmith!R105 ...)\n"
        "- **SLE24-16** - 8,880 (Tennsmith!R101, identity A101, column E101 "
        "'PRICE'; also M101 'U.S. LIST' 4,500)\n"
        "- **U-38** - no matching row in the indexed content searched\n"
    )

    def test_hyphenated_items_are_not_split(self):
        got = _runner().headline_values(self.ANSWER)
        assert got.get("U-22") == "1,777", got
        assert got.get("SLE24-16") == "8,880", got
        assert "U" not in got and "SLE24" not in got, got

    def test_items_stating_no_single_value_are_skipped(self):
        got = _runner().headline_values(self.ANSWER)
        # Ambiguous and absent items state no value; inventing one would be
        # the exact error the check exists to catch.
        assert "No. 381" not in got
        assert "TK Multi Wheel Gang Slitter" not in got
        assert "U-38" not in got

    def test_an_alias_note_does_not_hide_the_value(self):
        text = ("- **TK 1624 Slitter** (matched via 'Slitter') - 8,040 "
                "(Tinknocker!R101, identity A101)\n")
        assert _runner().headline_values(text) == {"TK 1624 Slitter": "8,040"}


class TestAsNumber:
    def test_numeric_strings_are_numbers(self):
        """After extraction a price column is often TEXT ('8880').

        A verifier that only accepts int/float reports a correct answer as a
        fabricated one, which trains people to ignore the check.
        """
        as_number = _runner()._as_number
        assert as_number("8880") == 8880.0
        assert as_number("1,777") == 1777.0
        assert as_number(1777) == 1777.0
        assert as_number("") is None
        assert as_number("Single Wheel Slitter") is None
        assert as_number(True) is None, "a bool is not a measurement"


class TestStructuredForIsIdentityNotRecency:
    """No execution id -> refuse. Two matches -> fail. Never pick one."""

    @staticmethod
    def _db(tmp_path, rows):
        import sqlite3
        db = tmp_path / "atom.db"
        con = sqlite3.connect(db)
        con.execute(
            "CREATE TABLE chat_messages (conversation_id TEXT, role TEXT, "
            "created_at TEXT, metadata_json TEXT)")
        con.executemany("INSERT INTO chat_messages VALUES (?,?,?,?)", rows)
        con.commit()
        con.close()
        return str(db)

    @staticmethod
    def _meta(execution_id, attempt):
        import json
        return json.dumps({
            "execution_id": execution_id,
            "pending_file_result": {
                "structured_result": {"attempt_id": attempt,
                                      "requested_items": ["U-22"]}},
        })

    def test_missing_execution_identity_refuses_rather_than_taking_latest(
            self, tmp_path):
        db = self._db(tmp_path, [
            ("s1", "assistant", "2026-01-01", self._meta("e-old", "a-old")),
        ])
        with pytest.raises(ValueError, match="explicit execution_id"):
            _runner().structured_for(db, "s1")

    def test_the_right_execution_is_returned(self, tmp_path):
        db = self._db(tmp_path, [
            ("s1", "assistant", "2026-01-01", self._meta("e-old", "a-old")),
            ("s1", "assistant", "2026-01-02", self._meta("e-new", "a-new")),
        ])
        rec = _runner().structured_for(db, "s1", "e-old")
        assert rec["attempt_id"] == "a-old", (
            "a neighbouring turn's record is not this turn's evidence")

    def test_duplicate_records_for_one_execution_fail_loudly(self, tmp_path):
        db = self._db(tmp_path, [
            ("s1", "assistant", "2026-01-01", self._meta("e-x", "a-1")),
            ("s1", "assistant", "2026-01-01", self._meta("e-x", "a-2")),
        ])
        with pytest.raises(AssertionError, match="ambiguous"):
            _runner().structured_for(db, "s1", "e-x")

    def test_no_record_for_this_execution_is_none(self, tmp_path):
        db = self._db(tmp_path, [
            ("s1", "assistant", "2026-01-01", self._meta("e-old", "a-old")),
        ])
        assert _runner().structured_for(db, "s1", "e-absent") is None


# ---------------------------------------------------------------------------
# #60  which carrier wins the active item set
# ---------------------------------------------------------------------------

class TestStoredRequestedItemsPrecedence:
    """The revised set has to survive every continuation, including a FAILED
    re-read.

    The item set can live in two places: the session's structured result row
    and the stored pending-file task. They are not written at the same moment
    -- the result row is written on every turn, the task only when a revision
    actually lands -- so a failed re-read leaves them disagreeing, and reading
    the wrong one resurrects the pre-correction list. That is the whole
    failure this lane exists to remove, so the precedence is pinned directly.
    """

    def test_the_result_row_wins_when_both_agree(self):
        session = {
            "_pending_file_result": {
                "structured_result": {"requested_items": ["A", "B"]}},
            FILE_TASK_SESSION_KEY: {"requested_targets": ["A", "B"]},
        }
        assert chat._stored_requested_items(session) == ["A", "B"]

    def test_a_failed_reread_cannot_revert_to_the_old_set(self):
        """A re-read that did not complete leaves the previous result row in
        place. The durable task carries the correction, so the correction must
        win -- otherwise the next turn reads the list the user just fixed."""
        session = {
            # stale: the PRE-correction set, left over from a failed re-read
            "_pending_file_result": {
                "structured_result": {"requested_items": ["A", "U-22", "C"]}},
            # authoritative: the task's revision landed
            FILE_TASK_SESSION_KEY: {"requested_targets": ["A", "U-38", "C"]},
        }
        assert chat._stored_requested_items(session) == ["A", "U-38", "C"], (
            "the pre-correction item set resurfaced; a continuation would "
            "resurrect the outgoing item")

    def test_the_task_carries_the_set_when_no_result_row_exists(self):
        """The restart case: hydration restores the task, not the result row,
        so a session with only the task must still know the objective."""
        session = {FILE_TASK_SESSION_KEY: {"requested_targets": ["A", "U-38"]}}
        assert chat._stored_requested_items(session) == ["A", "U-38"]

    def test_no_carriers_yields_nothing_rather_than_guessing(self):
        assert chat._stored_requested_items({}) == []
        assert chat._stored_requested_items(None) == []
