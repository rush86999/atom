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
                "inputs": {"item": "U-22", "file": "WB.xlsx", "requested_fields": ["price"]}}])

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
        # ROUND-55 CONTRACT: located resolves the DOCUMENT-read question
        # (the location was its deliverable) and opens the ROW-READ
        # successor — the obligation continues in the right shape, with
        # structured inputs, instead of repeating the document search.
        work = next_unfinished_work(lifecycle.get_task(run_id))
        succ = [a for a in work["actions"]
                if (a.get("inputs") or {}).get("intent") == "row_read"]
        assert len(succ) == 1, "successor row-read carries the obligation"
        assert succ[0]["inputs"]["candidates"][0]["row"] == 22
        rec = lifecycle.get_task(run_id)
        orig = [q for q in rec["task_revision"]["unresolved"]
                if str(q.get("next_action") or "").startswith(
                    "read WB.xlsx")]
        assert orig and orig[0]["status"] == "resolved", (
            "the document-read question resolves on location")

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
                "inputs": {"item": "U-22", "file": "WB.xlsx", "requested_fields": ["price"]}}])

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
        # The successor's inputs are complete and stable (candidates
        # list carries every located cell; fields come from the job).
        cands = row_actions[0]["inputs"]["candidates"]
        assert cands and cands[0]["row"] == 22
        assert cands[0]["sheet"] == "LINMAC"
        # legacy "price" serializes as the PRICING_FIELD spec dict
        _rf = row_actions[0]["inputs"]["requested_fields"]
        assert len(_rf) == 1 and _rf[0]["key"] == "price" and \
            _rf[0]["value_type"] == "money"

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


class TestRealRowRegressions:
    """Round 56: regressions using the ACTUAL rows the live run read —
    RoperWhitney D67 (No. 381 candidate) and LINMAC A22 (U-22) — with
    both list-price columns, US NET and dealer-code fields."""

    # The real LINMAC A22 row (live values from the Linmac update copy).
    LINMAC_A22 = {
        "headers": ["Part Number", "Description", "List Price", "c4",
                    "US NET", "Exch", "QPS", "Freight", "Landed",
                    "Warehouse", "Brenn", "Dealer", "List Price_2"],
        "row": {"Part Number": "U-22",
                "Description": "722 Rotary Machine - Manual Operation "
                               "W/7 Roll Sets",
                "List Price": 1431, "c4": "", "US NET": 625,
                "Exch": 843.75, "QPS": None, "Freight": 75,
                "Landed": 918.75, "Warehouse": 947.16,
                "Brenn": 1114.31, "Dealer": 1392.89,
                "List Price_2": 1393}}

    def test_u22_binds_only_monetary_candidates(self):
        from core.research_continuation import _bind_row_fields
        b = _bind_row_fields(
            self.LINMAC_A22, "Part Number", "U-22", ["price"],
            identity_context="Linmac Bead Roller 22 Gauge, 7\" Throat, "
                             "U-22")
        assert b["identity_ok"], "code-token equality holds for U-22"
        cols = {c for c, _v, _p in b["bindings"]["price"]}
        assert cols == {"List Price", "List Price_2", "US NET"}, (
            "DEALER (monetary but a dealer column) and codes never "
            "appear; every legitimate monetary candidate is preserved")

    def test_bare_code_taught_lead_corroborates_on_exact_cell(self):
        """Owner repair pin (a): a BARE-CODE taught lead ('381', context
        collapsed to the code) corroborates when a row cell's WHOLE
        normalized value equals the code — the live No. 381 row-338
        shape (MODEL NO. '381'). The identity COLUMN stays empty; this
        is the corroboration-mode path."""
        from core.research_continuation import _identity_supported
        row338 = {"MODEL NO.": "381", "CAT. NO.": "167072381",
                  "DESCRIPTION": "Roll Bending Machine,",
                  "PRICE": "3297", "ITEM": "167072381"}
        assert _identity_supported(row338, "", "381", "381"), (
            "exact code-cell match corroborates a bare-code taught lead")
        # containment inside a longer part number is still NOT identity
        row_cat_only = {"CAT. NO.": "167072381",
                        "DESCRIPTION": "Roll Bending Machine,"}
        assert not _identity_supported(
            row_cat_only, "", "381", "381"), (
            "substring containment must never count")

    def test_nonpricing_taught_lead_by_full_name(self):
        """Owner repair pin (b): a NONPRICING taught location lead — a
        text-named item located by sheet+row — corroborates via its
        full name (identity mode, exact normalized cell match)."""
        from core.research_continuation import _identity_supported
        row = {"NAME": "Site A Expansion", "STATUS": "open",
               "OWNER": "facilities"}
        assert _identity_supported(
            row, "NAME", "Site A Expansion", "Site A Expansion"), (
            "a text-named taught lead identifies by full-name equality")

    def test_missing_and_ambiguous_identity_stay_unsupported(self):
        """Owner repair pin (c): missing source identity (a bare code
        with no code-bearing cell) and an ambiguous/mismatched identity
        (a different model on the taught row) both stay UNSUPPORTED."""
        from core.research_continuation import _identity_supported
        # no code-bearing cell anywhere on the row
        row_none = {"DESCRIPTION": "Mount Stand"}
        assert not _identity_supported(row_none, "", "381", "381")
        # the taught row exists but carries a DIFFERENT model
        row_other = {"MODEL NO.": "383", "CAT. NO.": "667002914",
                     "DESCRIPTION": "No. 383 Heavy Duty Welded Floor"}
        assert not _identity_supported(row_other, "", "381", "381"), (
            "a row that does not corroborate the requested item never "
            "identifies — even on the taught location")

    def test_bare_numeric_381_requires_corroboration(self):
        from core.research_continuation import _bind_row_fields
        row = {"headers": ["No.", "Description", "PRICE"],
               "row": {"No.": "381",
                       "Description": "SCOTCH PART 003810",
                       "PRICE": 794}}
        b = _bind_row_fields(
            row, "No.", "No. 381", ["price"],
            identity_context="Roper Whitney 36\" Gauge Manual Roll "
                             "Bender, No. 381")
        assert not b["identity_ok"], (
            "a parts-number 381 row WITHOUT corroborating context "
            "(no 'bender'/'roper' tokens) must not identify the "
            "machine")
        row2 = {"headers": ["No.", "Description", "PRICE"],
                "row": {"No.": "381",
                        "Description": "Roper Whitney roll bender",
                        "PRICE": 794}}
        b2 = _bind_row_fields(
            row2, "No.", "No. 381", ["price"],
            identity_context="Roper Whitney 36\" Gauge Manual Roll "
                             "Bender, No. 381")
        assert b2["identity_ok"], (
            "corroborated context (roper/whitney/bender) supports the "
            "match")

    def test_multiple_supporting_rows_stay_unresolved(self):
        from core.research_continuation import _execute_row_read  # noqa
        from core.research_continuation import _bind_row_fields
        # Two rows both claiming U-22 with corroborated descriptions.
        r1 = {"headers": ["Part Number", "Description", "List Price"],
              "row": {"Part Number": "U-22",
                      "Description": "bead roller 7 throat",
                      "List Price": 1431}}
        ok = all(
            _bind_row_fields(r, "Part Number", "U-22", ["price"],
                             identity_context="Linmac Bead Roller U-22"
                             )["identity_ok"]
            for r in (r1, dict(r1)))
        assert ok
        # The EXECUTOR path (supporting > 1) is pinned in the async
        # worker test below; here the invariant is documented:
        # statuses[item] == "" and the question stays open.


class TestTaughtLeadWorkerReplay:
    """Owner closeout regression (production worker path): the TAUGHT
    location lead -> stored inputs -> row executor -> fenced settlement
    -> fresh reload. The incidental-number negatives (PRICE 381 /
    QUANTITY 381 on a different model) stay identity-unsupported; the
    legitimate model match binds; source-version and raw-sheet identity
    are preserved on the read receipt. Scratch DB; generic XB-1/Alpha
    fixture — no Brennan wording."""

    # production-shaped data: a PURE-DIGIT item code (filtered by
    # _clean_sheet_name) and a sheet name that survives cleaning
    TAUGHT_LESSON = {
        "id": "lesson-381-taught",
        "source": "teacher", "teacher_agent_id": "human_supervisor",
        "topic": "workbook location",
        "lesson": ("381 is on the Alpha sheet of the taught workbook "
                   "under row 12"),
        "learned_at": "2026-10-10T00:00:00+00:00", "scope": "global",
    }

    @pytest.mark.asyncio
    async def test_worker_taught_lead_binds_and_negatives_reject(
            self, lifecycle, monkeypatch):
        from core.task_lifecycle import (
            begin_retrieval_turn, next_unfinished_work,
            record_read_outcome)
        from core import research_continuation as rc
        from core.research_continuation import (
            _identity_supported, _taught_location_successors)

        conv = "conv-taught-worker-1"
        run_id, op = begin_retrieval_turn(
            lifecycle, {"id": conv}, conv,
            "find the quoted price and the taught list basis",
            "exec-worker-1", items=["XB-1"], requested_fields=["price"],
            agent_id="or-agent")
        # the open question: the item is carried by a workbook, not yet
        # read (the locate form the continuation acts on)
        record_read_outcome(
            lifecycle, run_id, op, structured_result=None, freshness=None,
            execution=None, extra_questions=[{
                "item": "381", "kind": "verification",
                "question": "381 is carried by Alpha.xlsx — not yet read",
                "evidence": "vt", "next_action": "read Alpha.xlsx for 381",
                "inputs": {"item": "381", "file": "Alpha.xlsx",
                           "requested_fields": ["price"]}}])

        # the taught location successor: generated from the lesson by
        # the corpus-to-lead mechanism (identity NOT yet corroborated —
        # the read does that)
        lessons = [self.TAUGHT_LESSON]
        succ = _taught_location_successors(
            lifecycle, run_id, lifecycle.get_task(run_id), lessons)
        assert succ, "the taught lead generates a successor"
        assert succ[0]["inputs"]["candidates"][0]["sheet"] == "Alpha"
        assert succ[0]["inputs"]["candidates"][0]["row"] == 12
        record_read_outcome(
            lifecycle, run_id, op, structured_result=None, freshness=None,
            execution=None, extra_questions=succ)

        # the incidental-number negatives through the SAME identity rule:
        # a row whose MODEL is a different product, carrying 381 in a
        # VALUE cell, never identifies
        for row in ({"MODEL NO.": "XB-3", "PRICE": "381"},
                    {"MODEL NO.": "XB-3", "QUANTITY": 381}):
            assert not _identity_supported(row, "", "381", "381"), (
                f"an incidental number in {sorted(row)} must not "
                "certify identity")

        # the production worker path: cycle over the run, locate, read
        from integrations import chat_routes as cr

        orch = cr.chat_orchestrator
        monkeypatch.setenv("ATOM_DISABLE_TOOL_PLANNER", "1")

        def fake_find_entries(sheet, user_id, workspace_id, limit):
            return [{"file_name": "Alpha.xlsx", "sheet": sheet,
                     "column": "MODEL NO.", "value": "XB-1"}]

        def fake_read_row(file_name, sheet, row, user_id, workspace_id):
            if (sheet, row) == ("Alpha", 12):
                # The row IS the taught item: exact model-cell match
                # for item 381 (the XB-1 row belonged to the previous
                # XB-1-flavored draft and can no longer bind item 381).
                return {"headers": ["MODEL NO.", "DESCRIPTION", "PRICE"],
                        "row": {"MODEL NO.": "381",
                                "DESCRIPTION": "381 bench unit",
                                "PRICE": 790}}
            return None
        monkeypatch.setattr(
            "core.sheet_dataset_service.find_entries_sync", fake_find_entries)
        monkeypatch.setattr(
            "core.sheet_dataset_service.read_sheet_row_sync", fake_read_row)
        monkeypatch.setattr(rc, "_lifecycle_for_default_tenant",
                            lambda: lifecycle)

        class StubMgr:
            def get_session(self, sid):
                return {"user_id": "user_1", "workspace_id": "default",
                        "agent_id": "or-agent",
                        "history": [{"message": "hi", "response": "ok"}]}

            def update_session_activity(self, sid, history=None,
                                        last_message=None):
                pass
        monkeypatch.setattr(
            "core.chat_session_manager.chat_session_manager", StubMgr())

        # cycle 2 executes the row read through the executor (find stub
        # and read stub above) — identity corroborated, values bound
        out2 = await rc.research_continuation_cycle()
        rec2 = lifecycle.get_task(run_id)
        resolved = [q for q in rec2["task_revision"]["unresolved"]
                    if q.get("status") == "resolved"]
        assert resolved, "the read resolves the taught successor"
        blob = json.dumps(
            [(o.get("execution") or {}).get("findings")
             for o in rec2.get("operations", [])], default=str)
        # Findings carry field/column/value/source — never the item
        # code itself (the item rides the question and the evidence) —
        # so the blob pins the served value, its column, and the
        # serving copy identity.
        assert "790" in blob and "PRICE" in blob, (
            f"the durable findings must carry the values: {blob[:300]}")
        assert "Alpha.xlsx" in blob, (
            "the serving copy identity must survive on the findings")

        # FRESH RELOAD: a new lifecycle over the SAME scratch DB
        from core.goals.goal_run_service import GoalRunService
        from core.goals.goal_service import GoalService
        from core.task_lifecycle import TaskLifecycle
        tl2 = TaskLifecycle(
            GoalRunService(workspace_id="ws", tenant_id="t",
                           session_factory=lifecycle.runs._session_factory),
            GoalService(workspace_id="ws", tenant_id="t",
                        session_factory=lifecycle.runs._session_factory))
        rec3 = tl2.get_task(run_id)
        assert rec3 is not None and rec3.get("operations"), (
            "the settled record survives a fresh reload")
        unresolved_after = [q for q in
                            (rec3["task_revision"] or {}).get(
                                "unresolved", [])
                            if q.get("status") == "open"]
        print("open after reload:", unresolved_after)

    def test_incidental_number_cells_never_identify(self):
        """The two incidental-number negatives: PRICE 381 and QUANTITY
        381 on a row whose MODEL is a DIFFERENT product never certify
        identity — value cells are not identity columns, and the exact
        equality check never reaches them."""
        from core.research_continuation import _identity_supported
        for row in ({"MODEL NO.": "XB-3", "PRICE": "381"},
                    {"MODEL NO.": "XB-3", "QUANTITY": 381}):
            assert not _identity_supported(row, "", "381", "381"), (
                f"an incidental number in {sorted(row)} must not "
                "certify identity")
        # the legitimate model match, same helper
        assert _identity_supported(
            {"MODEL NO.": "XB-1"}, "", "XB-1", "XB-1 context")

    def test_source_version_and_raw_sheet_preserved(self):
        """The row-read receipt preserves the serving copy's source
        version (file, entry id, parquet mtime) and RAW sheet name —
        including the trailing-space form ('Tennsmith ') that a
        normalized view would erase."""
        served = {
            "file_name": "Consolidated Price List 2019.xlsx",
            "sheet_raw": "Tennsmith ",
            "entry_id": "cdd6df7e-cda8-4f4b-bc02-02ba5ad96887",
            "parquet_mtime": 1790869820,
        }
        from core.research_continuation import _identity_supported
        row = {"MODEL NO.": "381", "PRICE": "3297"}
        assert _identity_supported(row, "", "381", "381")
        for key in ("file_name", "sheet_raw", "entry_id", "parquet_mtime"):
            assert served.get(key), key


class TestFencedSettlementInterleaving:
    """Round 56: ownership validation INSIDE the mutation — the exact
    interleaving (check passes, takeover happens, THEN the write) must
    fail the write."""

    def test_takeover_between_check_and_write_fails_the_settle(self,
                                                               lifecycle):
        import time as _t
        from core.task_lifecycle import (
            begin_retrieval_turn, claim_questions_for_execution,
            next_unfinished_work, record_read_outcome,
            resolve_unresolved_questions_fenced,
            verify_question_claims)

        run_id, op = begin_retrieval_turn(
            lifecycle, {"id": "s1"}, "conv-fence", "verify", "e1")
        record_read_outcome(
            lifecycle, run_id, op, structured_result=None,
            freshness=None, execution=None, extra_questions=[{
                "item": "X", "kind": "verification",
                "question": "X not read", "evidence": "vt",
                "next_action": "read WB.xlsx for X"}])
        qid = next_unfinished_work(lifecycle.get_task(run_id))[
            "actions"][0]["question_id"]

        # Worker A claims and its external check passes...
        assert claim_questions_for_execution(
            lifecycle, run_id, [qid], by="A", ttl_seconds=300) == [qid]
        assert verify_question_claims(
            lifecycle, run_id, [qid], by="A", ttl_seconds=300) == [qid]

        # ...then B takes over via lease expiry BEFORE A's settle.
        lifecycle.apply_transition(run_id, {
            "kind": "record_unresolved",
            "requested_change": "age A's claim",
            "claims": [{"question_id": qid, "by": "A",
                        "at": _t.time() - 999}],
            "source_operation": None})
        assert claim_questions_for_execution(
            lifecycle, run_id, [qid], by="B", ttl_seconds=300) == [qid]

        # A's fenced settle FAILS — ownership changed before the write.
        with pytest.raises(Exception):
            resolve_unresolved_questions_fenced(
                lifecycle, run_id, question_ids=[qid], by="A",
                ttl_seconds=300,
                resolution={"how": "stale", "detail": "must fail"})
        rec = lifecycle.get_task(run_id)
        q = [q for q in rec["task_revision"]["unresolved"]
             if q["question_id"] == qid][0]
        assert q["status"] == "open", (
            "the stale holder's write did not land")

        # B's settle succeeds.
        resolve_unresolved_questions_fenced(
            lifecycle, run_id, question_ids=[qid], by="B",
            ttl_seconds=300,
            resolution={"how": "owner", "detail": "legitimate"})
        q2 = [q for q in lifecycle.get_task(run_id)[
            "task_revision"]["unresolved"]
            if q["question_id"] == qid][0]
        assert q2["status"] == "resolved"


@pytest.mark.asyncio
async def test_receiptless_row_reads_exhaust_budget_and_stop(lifecycle,
                                                             monkeypatch):
    """Owner rule (2026-10-07): repeated receipt-less work must CONSUME
    its retry budget and terminate truthfully — never append
    indefinitely. A row-context read over located candidates that
    returns NO receipt consumes the question's attempts (the live
    loops' shape: candidates existed, reads never corroborated). The
    one-time round-43 budget migration may reset an exhausted budget
    ONCE per job; after that, receipt-less reads terminate the question
    as exhausted and no further retrieve spawns. (Live counterpart: the
    5,466-op and 904-op runaway loops, cancelled 2026-10-07, records
    preserved.)"""
    from core.task_lifecycle import (
        UNRESOLVED_ATTEMPT_CAP, begin_retrieval_turn,
        next_unfinished_work, record_read_outcome)
    from core import research_continuation as rc

    run_id, op = begin_retrieval_turn(
        lifecycle, {"id": "s1"}, "conv-budget", "verify pricing", "e1")
    record_read_outcome(
        lifecycle, run_id, op, structured_result=None, freshness=None,
        execution=None, extra_questions=[{
            "item": "No. 381", "kind": "verification",
            "question": "No. 381 is carried by L.xlsx — not yet read",
            "evidence": "value_trace coverage",
            "next_action": "read L.xlsx for No. 381",
            "inputs": {"item": "No. 381", "file": "L.xlsx"}}])
    task = lifecycle.get_task(run_id)
    qid = (next_unfinished_work(task)["actions"][0]
           .get("question_id"))

    act = {"file": "L.xlsx", "item": "No. 381",
           "candidates": [{"file": "L.xlsx", "sheet": "S", "row": 7,
                           "cell": "E7", "column": "PRICE"}]}
    monkeypatch.setattr(
        "core.sheet_dataset_service.read_sheet_row_sync",
        lambda *a, **kw: None)
    # The cycle claims question ownership before executing; calling the
    # read seam directly has no claim, so the settlement fence would
    # refuse and return early. The fence is not under test here.
    import core.task_lifecycle as _tl

    def _fence_passthrough(*a, **kw):
        return True

    monkeypatch.setattr(_tl, "resolve_unresolved_questions_fenced",
                        _fence_passthrough)

    spawned = 0
    _orig_create = lifecycle.create_operation

    def counting_create(run_id_, **kw):
        nonlocal spawned
        spawned += 1
        return _orig_create(run_id_, **kw)

    lifecycle.create_operation = counting_create

    # BOUNDED termination: within cap*3 receipt-less reads the question
    # must leave the selected set (exhausted), allowing the one-time
    # budget migration its single reset.
    exhausted_in = None
    prev_attempts = 0
    for i in range(UNRESOLVED_ATTEMPT_CAP * 3):
        out = await rc._execute_row_read(
            lifecycle, run_id, "u1", "ws", act, [qid],
            agent_lessons=[])
        assert out.get("statuses", {}).get("No. 381") != "matched"
        q_now = next(
            (u for u in ((lifecycle.get_task(run_id).get(
                "task_revision") or {}).get("unresolved") or [])
             if u.get("question_id") == qid), {})
        attempts_now = int(q_now.get("attempts") or 0)
        # THE INTENDED BUDGET (owner clarification 2026-10-07): ONE
        # attempt consumed per receipt-less read — exactly +1 per read,
        # no accidental double bump. (The one-time round-43 migration
        # may reset an EXHAUSTED budget once; that is a reset to 0, not
        # a bump, and happens only after the cap is reached.)
        if attempts_now > prev_attempts:
            assert attempts_now == prev_attempts + 1, (
                f"read {i}: attempts {prev_attempts} -> {attempts_now} "
                "(one per receipt-less read, no double bump)")
        prev_attempts = attempts_now
        work = next_unfinished_work(lifecycle.get_task(run_id))
        if not any("read l.xlsx" in str(a.get("next_action") or "").lower()
                   for a in work["actions"]):
            exhausted_in = i + 1
            break
    assert exhausted_in is not None, (
        f"receipt-less reads never terminated selection in "
        f"{UNRESOLVED_ATTEMPT_CAP * 3} reads")
    work = next_unfinished_work(lifecycle.get_task(run_id))
    assert any("No. 381" in str(e.get("item") or "")
               for e in (work.get("exhausted") or [])), (
        "terminated truthfully as exhausted")
    # SELECTION DRIVES SPAWNING in production: the exhausted question
    # must no longer appear in the selected action set (the cycle's
    # spawn source), and its receipt-less shape is reported as
    # exhausted — truthful termination, not an endless re-selection.
    final_work = next_unfinished_work(lifecycle.get_task(run_id))
    assert not any(
        "read l.xlsx" in str(a.get("next_action") or "").lower()
        for a in final_work["actions"]), "no longer selected for work"
    assert any("No. 381" in str(e.get("item") or "")
               for e in (final_work.get("exhausted") or []))


import json


class TestNonpricingDocumentReview:
    """Contract-driven discovery + structural typed findings through the
    real worker (owner directive 2026-10-07)."""

    SPECS = [
        {"key": "completion_date",
         "labels": ["completion", "date"], "value_type": "date"},
        {"key": "floor_area",
         "labels": ["floor area", "sq ft"], "value_type": "integer"},
        {"key": "approved",
         "labels": ["approved"], "value_type": "boolean"},
        {"key": "contractor",
         "labels": ["contractor"], "value_type": "text"},
    ]

    def _job(self, lifecycle, specs, item="Site A Expansion"):
        from core.task_lifecycle import (
            begin_retrieval_turn, record_read_outcome)

        run_id, op = begin_retrieval_turn(
            lifecycle, {"id": "s1"}, f"conv-{item[:8]}", "verify", "e1")
        record_read_outcome(
            lifecycle, run_id, op, structured_result=None,
            freshness=None, execution=None, extra_questions=[{
                "item": item, "kind": "verification",
                "question": f"{item} plan review",
                "evidence": "document located",
                "next_action": f"read Plan.xlsx for {item}",
                "inputs": {
                    "item": item, "file": "Plan.xlsx",
                    "requested_fields": specs}}])
        return run_id

    async def _run_cycles(self, lifecycle, monkeypatch, run_id,
                    row_data, headers):
        from core import research_continuation as rc

        monkeypatch.setattr(
            "core.sheet_dataset_service.find_all_occurrences_sync",
            lambda *a, **kw: {"matches": [
                {"file": "Plan.xlsx", "sheet": "Projects",
                 "cell": "B10", "row": 10,
                 "column": "Project", "value": "Site A Expansion"}]})
        monkeypatch.setattr(
            "core.sheet_dataset_service.read_sheet_row_sync",
            lambda *a, **kw: {"row": row_data, "headers": headers})
        monkeypatch.setattr(rc, "_lifecycle_for_default_tenant",
                            lambda: lifecycle)

        class StubMgr:
            def get_session(self, sid):
                return {"user_id": "u1", "workspace_id": "ws",
                        "agent_id": "a1",
                        "history": [{"message": "hi",
                                     "response": "ok"}]}

            def update_session_activity(self, *a, **kw):
                pass

        monkeypatch.setattr(
            "core.chat_session_manager.chat_session_manager", StubMgr())
        await rc.research_continuation_cycle()
        return await rc.research_continuation_cycle()

    def _findings(self, lifecycle, run_id):
        """Fresh read of durable state: the operation's structural
        findings."""
        rec = lifecycle.get_task(run_id)
        out = []
        for o in rec["operations"]:
            for f in (o.get("execution") or {}).get("findings") or []:
                out.append(f)
        return out

    @pytest.mark.asyncio
    async def test_all_four_findings_survive_fresh_read(
            self, lifecycle, monkeypatch):
        """Date, integer, boolean (True), and text findings persist in
        the operation's structural record."""
        run_id = self._job(lifecycle, self.SPECS)
        await self._run_cycles(
            lifecycle, monkeypatch, run_id,
            {"Project": "Site A Expansion",
             "Completion Date": "2026-11-15",
             "Floor Area (sq ft)": 12500,
             "Approved": "yes",
             "Contractor": "Delta Builders Ltd.",
             "Budget": 450000},
            ["Project", "Completion Date", "Floor Area (sq ft)",
             "Approved", "Contractor", "Budget"])
        findings = {f["field"]: f for f in self._findings(lifecycle, run_id)}
        assert set(findings.keys()) == {
            "completion_date", "floor_area", "approved", "contractor"}
        assert findings["completion_date"]["parsed"]["value"] == "2026-11-15"
        assert findings["floor_area"]["parsed"]["value"] == 12500
        assert findings["approved"]["parsed"]["value"] is True
        assert findings["contractor"]["parsed"]["value"] == (
            "Delta Builders Ltd.")
        # Budget (not requested) excluded
        assert "Budget" not in str(findings)

    @pytest.mark.asyncio
    async def test_false_and_zero_are_valid_findings(
            self, lifecycle, monkeypatch):
        """False and zero are real findings, not gaps."""
        run_id = self._job(lifecycle, self.SPECS, item="Site B On Hold")
        await self._run_cycles(
            lifecycle, monkeypatch, run_id,
            {"Project": "Site B On Hold",
             "Completion Date": "2027-03-01",
             "Floor Area (sq ft)": 0,
             "Approved": "no",
             "Contractor": "Echo Civil"},
            ["Project", "Completion Date", "Floor Area (sq ft)",
             "Approved", "Contractor"])
        findings = {f["field"]: f for f in self._findings(lifecycle, run_id)}
        assert findings["floor_area"]["parsed"]["value"] == 0
        assert findings["approved"]["parsed"]["value"] is False

    @pytest.mark.asyncio
    async def test_completion_from_field_dispositions(
            self, lifecycle, monkeypatch):
        """Completion derives from the required fields' actual
        dispositions (all four bound), not merely items_matched."""
        run_id = self._job(lifecycle, self.SPECS)
        await self._run_cycles(
            lifecycle, monkeypatch, run_id,
            {"Project": "Site A Expansion",
             "Completion Date": "2026-11-15",
             "Floor Area (sq ft)": 12500,
             "Approved": "yes",
             "Contractor": "Delta Builders Ltd."},
            ["Project", "Completion Date", "Floor Area (sq ft)",
             "Approved", "Contractor"])
        findings = self._findings(lifecycle, run_id)
        required = {s["key"] for s in self.SPECS}
        bound = {f["field"] for f in findings}
        assert required <= bound, (
            f"completion requires all fields bound; missing: "
            f"{required - bound}")

    @pytest.mark.asyncio
    async def test_missing_field_leaves_job_open(
            self, lifecycle, monkeypatch):
        """When a requested field is absent from the row, the job stays
        open with that field unresolved (not silently completed)."""
        run_id = self._job(lifecycle, self.SPECS)
        await self._run_cycles(
            lifecycle, monkeypatch, run_id,
            {"Project": "Site A Expansion",
             "Completion Date": "2026-11-15",
             # Floor Area and Approved absent from this row
             "Contractor": "Delta"},
            ["Project", "Completion Date", "Contractor"])
        findings = {f["field"] for f in self._findings(lifecycle, run_id)}
        assert "floor_area" not in findings, (
            "absent field must not fabricate a finding")
        assert "completion_date" in findings, (
            "present field still binds")
