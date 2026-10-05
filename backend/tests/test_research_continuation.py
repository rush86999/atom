# -*- coding: utf-8 -*-
"""Durable research continuation (round 52): the recurring worker that
finishes authorized read jobs after the interactive turn ends."""
from __future__ import annotations

import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("TESTING", "1")

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from core.models import GoalObjective, GoalRun, TaskOperationRecord
from core.goals.goal_run_service import GoalRunService
from core.goals.goal_service import GoalService
from core.task_lifecycle import TaskLifecycle


@pytest.fixture
def lifecycle(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path}/rc_test.db")
    for table in (GoalObjective.__table__, GoalRun.__table__,
                  TaskOperationRecord.__table__):
        table.create(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    return TaskLifecycle(
        GoalRunService(workspace_id="ws", tenant_id="t",
                       session_factory=factory),
        GoalService(workspace_id="ws", tenant_id="t",
                    session_factory=factory))


@pytest.mark.asyncio
async def test_cycle_executes_queued_read_and_retires(lifecycle,
                                                      monkeypatch):
    """A price-bearing per-item match retires the question; a second
    cycle executes nothing (no duplicate)."""
    from core.task_lifecycle import (
        begin_retrieval_turn, next_unfinished_work, record_read_outcome)
    from core import research_continuation as rc

    run_id, op = begin_retrieval_turn(
        lifecycle, {"id": "s1"}, "conv-rc", "verify pricing", "e1")
    record_read_outcome(
        lifecycle, run_id, op, structured_result=None, freshness=None,
        execution=None, extra_questions=[{
            "item": "SLE24-16", "kind": "verification",
            "question": "SLE24-16 is carried by X.xlsx — not yet read",
            "evidence": "value_trace coverage",
            "next_action": "read X.xlsx for SLE24-16",
            "inputs": {"item": "SLE24-16", "file": "X.xlsx"}}])

    def fake_find_all(value, user_id, workspace_id, file_name=None,
                      max_matches=8, **kw):
        return {"matches": [
            {"file": "X.xlsx", "sheet": "Tennsmith", "cell": "E101",
             "column": "PRICE", "value": "8984"}]}

    monkeypatch.setattr(
        "core.sheet_dataset_service.find_all_occurrences_sync",
        fake_find_all)
    monkeypatch.setattr(rc, "_lifecycle_for_default_tenant",
                        lambda: lifecycle)

    class StubMgr:
        def get_session(self, sid):
            return {"user_id": "u1", "workspace_id": "ws",
                    "agent_id": "a1",
                    "history": [{"message": "hi", "response": "ok"}]}

        def update_session_activity(self, sid, history=None,
                                    last_message=None):
            pass

    monkeypatch.setattr(
        "core.chat_session_manager.chat_session_manager", StubMgr())
    out = await rc.research_continuation_cycle()
    assert out["reads"] == 1 and out["items_matched"] == 1
    work = next_unfinished_work(lifecycle.get_task(run_id))
    # The READ question is retired; the freshness successor (correctly)
    # may remain open for a saved-copy match.
    assert not any(str(a.get("next_action") or "").lower().startswith(
        "read x.xlsx") for a in work["actions"]), "price match retires"
    assert all(
        "freshness" in str(a.get("question") or "").lower()
        for a in work["actions"] if "SLE24-16" in str(a.get("item"))), (
        "what remains is the freshness obligation, not the read")

    out2 = await rc.research_continuation_cycle()
    assert out2["reads"] == 0, "no duplicate execution"


@pytest.mark.asyncio
async def test_cycle_respects_missing_identity(lifecycle, monkeypatch):
    """No session identity -> the job is left durable and listed; nothing
    executes (authorization + identity discipline)."""
    from core.task_lifecycle import (
        begin_retrieval_turn, record_read_outcome)
    from core import research_continuation as rc

    run_id, op = begin_retrieval_turn(
        lifecycle, {"id": "s1"}, "conv-rc2", "verify", "e1")
    record_read_outcome(
        lifecycle, run_id, op, structured_result=None, freshness=None,
        execution=None, extra_questions=[{
            "item": "X", "kind": "verification",
            "question": "X is carried by Y — not yet read",
            "evidence": "vt", "next_action": "read Y.xlsx for X"}])

    monkeypatch.setattr(rc, "_lifecycle_for_default_tenant",
                        lambda: lifecycle)

    class NoSessionMgr:
        def get_session(self, sid):
            return None

    monkeypatch.setattr(
        "core.chat_session_manager.chat_session_manager", NoSessionMgr())
    out = await rc.research_continuation_cycle()
    assert out["reads"] == 0


@pytest.mark.asyncio
async def test_worker_start_is_idempotent():
    from core import research_continuation as rc

    async def scenario():
        first = rc.start_research_continuation()
        second = rc.start_research_continuation()
        await rc.stop_research_continuation()
        return first, second

    first, second = await asyncio.wait_for(scenario(), timeout=10)
    assert first is True and second is False, "idempotent start"


class TestPerItemEvidenceNegativeControls:
    """Round 53: a document-level receipt never resolves grouped items."""

    def _mk(self, lifecycle, conv, items_docs):
        from core.task_lifecycle import (
            begin_retrieval_turn, record_read_outcome)
        run_id, op = begin_retrieval_turn(
            lifecycle, {"id": "s1"}, conv, "verify pricing", "e1")
        qs = [{"item": it, "kind": "verification",
               "question": f"{it} is carried by {doc} — not yet read",
               "evidence": "value_trace coverage",
               "next_action": f"read {doc} for {it}",
               "inputs": {"item": it, "file": doc}}
              for it, doc in items_docs]
        record_read_outcome(
            lifecycle, run_id, op, structured_result=None, freshness=None,
            execution=None, extra_questions=qs)
        return run_id

    @pytest.mark.asyncio
    async def test_located_without_price_stays_open(self, lifecycle,
                                                    monkeypatch):
        """NEGATIVE CONTROL: a readable workbook whose only match for the
        item is an identity cell (Part Number) — located, price NOT
        read — the question must stay open."""
        from core.task_lifecycle import (
            begin_retrieval_turn, next_unfinished_work,
            record_read_outcome)
        from core import research_continuation as rc

        run_id, op = begin_retrieval_turn(
            lifecycle, {"id": "s1"}, "conv-n1", "verify", "e1")
        record_read_outcome(
            lifecycle, run_id, op, structured_result=None, freshness=None,
            execution=None, extra_questions=[{
                "item": "U-22", "kind": "verification",
                "question": "U-22 is carried by WB.xlsx — not yet read",
                "evidence": "vt",
                "next_action": "read WB.xlsx for U-22",
                "inputs": {"item": "U-22", "file": "WB.xlsx"}}])

        def fake_find_all(value, user_id, workspace_id, file_name=None,
                          max_matches=8, **kw):
            if value == "U-22":
                return {"matches": [
                    {"file": "WB.xlsx", "sheet": "LINMAC", "cell": "A22",
                     "column": "Part Number", "value": "U-22"}]}
            return {"matches": []}

        monkeypatch.setattr(
            "core.sheet_dataset_service.find_all_occurrences_sync",
            fake_find_all)
        monkeypatch.setattr(rc, "_lifecycle_for_default_tenant",
                            lambda: lifecycle)

        class StubMgr:
            def get_session(self, sid):
                return {"user_id": "u1", "workspace_id": "ws",
                        "agent_id": "a1",
                        "history": [{"message": "hi", "response": "ok"}]}

            def update_session_activity(self, sid, history=None,
                                        last_message=None):
                pass

        monkeypatch.setattr(
            "core.chat_session_manager.chat_session_manager", StubMgr())
        out = await rc.research_continuation_cycle()
        assert out["reads"] == 1 and out["items_located"] == 1
        assert out["items_matched"] == 0
        work = next_unfinished_work(lifecycle.get_task(run_id))
        assert any(
            "read WB.xlsx" in str(a.get("next_action") or "")
            for a in work["actions"]), (
            "located-without-price keeps its READ action open")

    @pytest.mark.asyncio
    async def test_no_match_at_all_stays_open(self, lifecycle, monkeypatch):
        """NEGATIVE CONTROL: a readable workbook containing NONE of the
        requested items — nothing resolves, no absence is claimed."""
        from core.task_lifecycle import (
            begin_retrieval_turn, next_unfinished_work,
            record_read_outcome)
        from core import research_continuation as rc

        run_id, op = begin_retrieval_turn(
            lifecycle, {"id": "s1"}, "conv-n2", "verify", "e1")
        record_read_outcome(
            lifecycle, run_id, op, structured_result=None, freshness=None,
            execution=None, extra_questions=[{
                "item": "Ghost", "kind": "verification",
                "question": "Ghost is carried by WB.xlsx — not yet read",
                "evidence": "vt",
                "next_action": "read WB.xlsx for Ghost",
                "inputs": {"item": "Ghost", "file": "WB.xlsx"}}])

        monkeypatch.setattr(
            "core.sheet_dataset_service.find_all_occurrences_sync",
            lambda *a, **kw: {"matches": []})
        monkeypatch.setattr(rc, "_lifecycle_for_default_tenant",
                            lambda: lifecycle)

        class StubMgr:
            def get_session(self, sid):
                return {"user_id": "u1", "workspace_id": "ws",
                        "agent_id": "a1",
                        "history": [{"message": "hi", "response": "ok"}]}

            def update_session_activity(self, sid, history=None,
                                        last_message=None):
                pass

        monkeypatch.setattr(
            "core.chat_session_manager.chat_session_manager", StubMgr())
        out = await rc.research_continuation_cycle()
        assert out["items_matched"] == 0
        work = next_unfinished_work(lifecycle.get_task(run_id))
        assert any(
            "read WB.xlsx" in str(a.get("next_action") or "")
            for a in work["actions"]), "no match keeps the read open"

    def test_classification_rules(self):
        from core.research_continuation import _classify_match
        assert _classify_match({"column": "Unit Price",
                                "value": "8984"}) == "matched"
        assert _classify_match({"column": "Part Number",
                                "value": "U-22"}) == "located"
        assert _classify_match({"column": "", "value": "$1,631.00"}) == \
            "matched"
        assert _classify_match({"column": "Description",
                                "value": "roller"}) == "located"

    def test_durable_claim_is_exclusive(self, lifecycle):
        from core.task_lifecycle import (
            begin_retrieval_turn, claim_questions_for_execution,
            next_unfinished_work, record_read_outcome)

        run_id, op = begin_retrieval_turn(
            lifecycle, {"id": "s1"}, "conv-cl", "verify", "e1")
        record_read_outcome(
            lifecycle, run_id, op, structured_result=None, freshness=None,
            execution=None, extra_questions=[{
                "item": "X", "kind": "verification",
                "question": "X not yet read", "evidence": "vt",
                "next_action": "read WB.xlsx for X"}])
        qid = next_unfinished_work(lifecycle.get_task(run_id))[
            "actions"][0]["question_id"]
        first = claim_questions_for_execution(
            lifecycle, run_id, [qid], by="worker-A", ttl_seconds=120)
        second = claim_questions_for_execution(
            lifecycle, run_id, [qid], by="worker-B", ttl_seconds=120)
        assert first == [qid] and second == [], (
            "a fresh claim by another worker is refused")
        # Re-claim by the SAME worker refreshes (no self-deadlock).
        again = claim_questions_for_execution(
            lifecycle, run_id, [qid], by="worker-A", ttl_seconds=120)
        assert again == [qid]


class TestRowContextSuccessor:
    """Round 54: located cell → persisted row-read action → actual read
    → evidence-bound disposition → completed action not re-selected."""

    def _row_result(self, row):
        return {"headers": list(row.keys()), "row": row}

    @pytest.mark.asyncio
    async def test_located_spawns_row_read_successor_and_it_resolves(
            self, lifecycle, monkeypatch):
        from core.task_lifecycle import (
            UNRESOLVED_ATTEMPT_CAP, begin_retrieval_turn,
            next_unfinished_work, record_read_outcome)
        from core import research_continuation as rc

        run_id, op = begin_retrieval_turn(
            lifecycle, {"id": "s1"}, "conv-rr", "verify", "e1")
        record_read_outcome(
            lifecycle, run_id, op, structured_result=None, freshness=None,
            execution=None, extra_questions=[{
                "item": "U-22", "kind": "verification",
                "question": "U-22 is carried by WB.xlsx — not yet read",
                "evidence": "vt", "next_action": "read WB.xlsx for U-22",
                "inputs": {"item": "U-22", "file": "WB.xlsx"}}])

        # Document read: identity-only match -> located + successor.
        def fake_find_all(value, user_id, workspace_id, file_name=None,
                          max_matches=8, **kw):
            return {"matches": [
                {"file": "WB.xlsx", "sheet": "LINMAC", "cell": "A22",
                 "column": "Part Number", "value": "U-22"}]}
        monkeypatch.setattr(
            "core.sheet_dataset_service.find_all_occurrences_sync",
            fake_find_all)
        # Row read: single price column.
        monkeypatch.setattr(
            "core.sheet_dataset_service.read_sheet_row_sync",
            lambda *a, **kw: self._row_result({
                "Part Number": "U-22", "Description": "bead roller",
                "List Price": 1777}))

        monkeypatch.setattr(rc, "_lifecycle_for_default_tenant",
                            lambda: lifecycle)

        class StubMgr:
            def get_session(self, sid):
                return {"user_id": "u1", "workspace_id": "ws",
                        "agent_id": "a1",
                        "history": [{"message": "hi", "response": "ok"}]}

            def update_session_activity(self, sid, history=None,
                                        last_message=None):
                pass

        monkeypatch.setattr(
            "core.chat_session_manager.chat_session_manager", StubMgr())
        out1 = await rc.research_continuation_cycle()
        assert out1["items_located"] == 1
        work = next_unfinished_work(lifecycle.get_task(run_id))
        row_actions = [a for a in work["actions"]
                       if (a.get("inputs") or {}).get("intent")
                       == "row_read"]
        assert len(row_actions) == 1, "successor created"
        # The successor's inputs are complete and stable.
        assert row_actions[0]["inputs"]["row"] == 22
        assert row_actions[0]["inputs"]["sheet"] == "LINMAC"
        assert row_actions[0]["inputs"]["requested_fields"] == ["price"]

        # Cycle 2 completes the row read (grouping keeps doc and row
        # reads distinct): the located state turns into evidence.
        out2 = await rc.research_continuation_cycle()
        assert out2["items_matched"] >= 1
        work2 = next_unfinished_work(lifecycle.get_task(run_id))
        assert not any(
            (a.get("inputs") or {}).get("intent") == "row_read"
            for a in work2["actions"]), "completed row-read retired"
        # And a THIRD cycle re-locates without duplicating successors:
        # no open row-read reappears, and exactly ONE resolved twin
        # exists in the record.
        out3 = await rc.research_continuation_cycle()
        work3 = next_unfinished_work(lifecycle.get_task(run_id))
        assert not any(
            (a.get("inputs") or {}).get("intent") == "row_read"
            for a in work3["actions"]), "resolved successor stays retired"
        rec3 = lifecycle.get_task(run_id)
        twins = [q for q in rec3["task_revision"]["unresolved"]
                 if (q.get("inputs") or {}).get("intent") == "row_read"]
        assert len(twins) == 1 and twins[0]["status"] == "resolved", (
            "re-location does not duplicate the resolved successor")

    @pytest.mark.asyncio
    async def test_ambiguous_price_columns_preserved_as_decision(
            self, lifecycle, monkeypatch):
        from core.task_lifecycle import (
            begin_retrieval_turn, next_unfinished_work,
            record_read_outcome)
        from core import research_continuation as rc

        run_id, op = begin_retrieval_turn(
            lifecycle, {"id": "s1"}, "conv-am", "verify", "e1")
        record_read_outcome(
            lifecycle, run_id, op, structured_result=None, freshness=None,
            execution=None, extra_questions=[{
                "item": "U-22", "kind": "verification",
                "question": "U-22 row read",
                "evidence": "located",
                "next_action": "read row LINMAC!A22 of WB.xlsx",
                "inputs": {
                    "service": "datasets", "intent": "row_read",
                    "file": "WB.xlsx", "sheet": "LINMAC", "row": 22,
                    "identity_column": "Part Number",
                    "identity_cell": "A22", "item": "U-22",
                    "requested_fields": ["price"]}}])
        monkeypatch.setattr(
            "core.sheet_dataset_service.read_sheet_row_sync",
            lambda *a, **kw: self._row_result({
                "Part Number": "U-22",
                "List Price": 1431, "List Price_2": 1393,
                "Dealer": 1392.89}))
        monkeypatch.setattr(rc, "_lifecycle_for_default_tenant",
                            lambda: lifecycle)

        class StubMgr:
            def get_session(self, sid):
                return {"user_id": "u1", "workspace_id": "ws",
                        "history": [{"message": "hi", "response": "ok"}]}

            def update_session_activity(self, sid, history=None,
                                        last_message=None):
                pass

        monkeypatch.setattr(
            "core.chat_session_manager.chat_session_manager", StubMgr())
        out = await rc.research_continuation_cycle()
        assert out["items_matched"] == 1
        rec = lifecycle.get_task(run_id)
        decisions = [q for q in rec["task_revision"]["unresolved"]
                     if q.get("kind") == "business_decision"]
        assert decisions, "ambiguity opens an owner decision"
        assert "List Price=1431" in decisions[0]["question"] and (
            "List Price_2=1393" in decisions[0]["question"]), (
            "every candidate is preserved in the decision")

    @pytest.mark.asyncio
    async def test_row_lacking_field_is_a_scoped_finding(
            self, lifecycle, monkeypatch):
        from core.task_lifecycle import (
            begin_retrieval_turn, next_unfinished_work,
            record_read_outcome)
        from core import research_continuation as rc

        run_id, op = begin_retrieval_turn(
            lifecycle, {"id": "s1"}, "conv-nf", "verify", "e1")
        record_read_outcome(
            lifecycle, run_id, op, structured_result=None, freshness=None,
            execution=None, extra_questions=[{
                "item": "X1", "kind": "verification",
                "question": "X1 row read", "evidence": "located",
                "next_action": "read row S!A5 of WB.xlsx",
                "inputs": {
                    "service": "datasets", "intent": "row_read",
                    "file": "WB.xlsx", "sheet": "S", "row": 5,
                    "identity_column": "Part Number",
                    "identity_cell": "A5", "item": "X1",
                    "requested_fields": ["price"]}}])
        monkeypatch.setattr(
            "core.sheet_dataset_service.read_sheet_row_sync",
            lambda *a, **kw: self._row_result({
                "Part Number": "X1", "Description": "thing"}))
        monkeypatch.setattr(rc, "_lifecycle_for_default_tenant",
                            lambda: lifecycle)

        class StubMgr:
            def get_session(self, sid):
                return {"user_id": "u1", "workspace_id": "ws",
                        "history": [{"message": "hi", "response": "ok"}]}

            def update_session_activity(self, sid, history=None,
                                        last_message=None):
                pass

        monkeypatch.setattr(
            "core.chat_session_manager.chat_session_manager", StubMgr())
        out = await rc.research_continuation_cycle()
        work = next_unfinished_work(lifecycle.get_task(run_id))
        assert not any(
            (a.get("inputs") or {}).get("intent") == "row_read"
            for a in work["actions"]), (
            "a scoped absence retires the row-read (finding recorded)")


class TestClaimSafety:
    """Round 54: claims are atomic conditional writes (CAS retry re-runs
    compute on fresh state); lease expiry transfers ownership; a stale
    holder must not settle."""

    def test_two_workers_over_one_store(self, lifecycle):
        from core.task_lifecycle import (
            TaskLifecycle, begin_retrieval_turn,
            claim_questions_for_execution, next_unfinished_work,
            record_read_outcome, verify_question_claims)

        run_id, op = begin_retrieval_turn(
            lifecycle, {"id": "s1"}, "conv-2w", "verify", "e1")
        record_read_outcome(
            lifecycle, run_id, op, structured_result=None,
            freshness=None, execution=None, extra_questions=[{
                "item": "X", "kind": "verification",
                "question": "X not read", "evidence": "vt",
                "next_action": "read WB.xlsx for X"}])
        qid = next_unfinished_work(lifecycle.get_task(run_id))[
            "actions"][0]["question_id"]

        worker_a = lifecycle
        worker_b = TaskLifecycle(lifecycle.runs, lifecycle.goals)
        a = claim_questions_for_execution(
            worker_a, run_id, [qid], by="A", ttl_seconds=120)
        b = claim_questions_for_execution(
            worker_b, run_id, [qid], by="B", ttl_seconds=120)
        assert a == [qid] and b == [], "atomic: B refuses A's fresh claim"

        # Lease expiry: B re-claims after A's TTL lapses.
        import time as _t
        worker_a.apply_transition(run_id, {
            "kind": "record_unresolved",
            "requested_change": "age A's claim past TTL",
            "claims": [{"question_id": qid, "by": "A",
                        "at": _t.time() - 999}],
            "source_operation": None,
        })
        b2 = claim_questions_for_execution(
            worker_b, run_id, [qid], by="B", ttl_seconds=120)
        assert b2 == [qid], "expired lease transfers to B"

        # Stale holder A must not settle B's question.
        assert verify_question_claims(
            worker_a, run_id, [qid], by="A", ttl_seconds=120) == []
        assert verify_question_claims(
            worker_b, run_id, [qid], by="B", ttl_seconds=120) == [qid]
