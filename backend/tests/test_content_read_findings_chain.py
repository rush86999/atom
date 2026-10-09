# -*- coding: utf-8 -*-
"""The durable chain: value-trace discovery -> durable pending read ->
content read -> typed findings -> fresh reload -> drafting contract.

The captured failure (planned=False, conv val-A-r1-bb75f): the confirmed-
file read returned 4,828 chars of real rows and the settle recorded
findings: 0. Two gate predicates were false and neither was pinned:

1. the settle's findings converter was fed the SEARCH-receipt sub-dict
   (whose ``structured_result``/``storage_read`` keys are structurally
   absent — it carries ``structured_keys``, the key NAMES), so the
   converter's input predicate failed and the read's row values never
   became typed findings;
2. the pending read's requested-value obligation sat at the question's
   TOP level, which ``_normalize_question`` drops — the content read
   received an empty field contract and bound nothing
   (``scope_missing_fields``).

These pins hold the chain end to end through the production functions
(the spawner, the settlement, the row/document executors, the existing
receipt converter, the drafting adapter) against a scratch database.
Negative controls hold the guardrails: discovery resolves no requested
value, receiptless prose yields no findings, and a multi-column row
persists candidates (each with its basis), never a first-picked price.
"""
from __future__ import annotations

import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("TESTING", "1")

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.models import GoalObjective, GoalRun, TaskOperationRecord
from core.goals.goal_run_service import GoalRunService
from core.goals.goal_service import GoalService
from core.task_lifecycle import TaskLifecycle

# The captured value-trace receipt (live log, conv val-A-r1-bb75f).
VALUE_TRACE_RECEIPT = {
    "dispatched": True, "retrieved": True, "bounded_absence": False,
    "receipt": {
        "structured_keys": [], "searched_threads": 0,
        "source_observations": 0, "read_outcomes": 0,
        "datasets_search": {},
        "value_trace_coverage": {"SLE24-16": [
            "Consolidated Price List 2019.xlsx",
            "Leads - Sarp follow up 4-1-2025.xlsx",
            "PRICE VIPUL (6).xlsx"]},
        "value_trace_items": 2, "coverage_items": []}}

# The confirmed-file read's receipt — the real structured-record shape a
# named-file read stamps on its storage_read meta.
CONTENT_READ_META = {
    "service": "datasets",
    "file_name": "Consolidated Price List 2019.xlsx",
    "content_hash": "ce61dd3d40cac83d39bd702e4617b91df061c962",
    "ingested_at": "2026-10-03T01:34:18",
    "identity_verified": True,
    "completed": True,
    "coverage_complete": True,
    "structured_result": {
        "schema_version": "structured-result-2",
        "source_identity": {
            "file_name": "Consolidated Price List 2019.xlsx",
            "service": "datasets",
            "source": "zoho_workdrive",
            "resource_id": "9ef83433837cdf6b841b6b7604d64e24dab42",
            "content_hash": "ce61dd3d40cac83d39bd702e4617b91df061c962",
            "ingested_at": "2026-10-03T01:34:18",
            "source_modified_at": None,
            "live_vs_saved": "saved copy",
            "evidence_kind": "materialized_copy",
        },
        "evidence_revision": "ce61dd3d:2026-10-03",
        "attempt_id": "a1",
        "evidence_action": "new_read",
        "requested_items": ["SLE24-16"],
        "requested_fields": ["price"],
        "targets": [{
            "item": "SLE24-16",
            "identity": {"status": "single", "candidates": [
                {"ref": "Tennsmith !R101"}]},
            "field": {"status": "single", "values": [
                {"col": "C101", "basis": "U.S. LIST", "kind": "number",
                 "value": 8984.0, "display": "8,984"}]},
            "retrieval": {"status": "searched", "error_category": None},
        }],
        "coverage": {"read_status": "success"},
    },
}

TENNSMITH_ROW = {
    "MODEL NO.": "SLE24-16",
    "Description": "Single Wheel Slitter",
    "U.S. LIST": "8,984",
    "U.S. COST": "7,100",
    "CANADIAN COST": "9,450",
    "DEALER CODE": "K",
}


@pytest.fixture()
def lifecycle(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path}/content_read_chain.db")
    for table in (GoalObjective.__table__, GoalRun.__table__,
                  TaskOperationRecord.__table__):
        table.create(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    tl = TaskLifecycle(
        GoalRunService(workspace_id="ws", tenant_id="t",
                       session_factory=factory),
        GoalService(workspace_id="ws", tenant_id="t",
                    session_factory=factory))
    tl._test_factory = factory
    return tl


def _fresh(lifecycle):
    """A SECOND lifecycle over the same durable store — the fresh-reload
    proof: new services, new instance, reads only what was persisted."""
    factory = lifecycle._test_factory
    return TaskLifecycle(
        GoalRunService(workspace_id="ws", tenant_id="t",
                       session_factory=factory),
        GoalService(workspace_id="ws", tenant_id="t",
                    session_factory=factory))


def _settle_value_trace(tl, run_id, op_id, items, ask_fields):
    """The production chain settle's question step: the value-trace
    receipt creates the durable pending read (the content-read action)."""
    from core.task_lifecycle import record_read_outcome
    from integrations.chat_orchestrator import _value_trace_pending_reads

    questions = _value_trace_pending_reads(
        VALUE_TRACE_RECEIPT, requested_fields=list(ask_fields))
    record_read_outcome(tl, run_id, op_id, structured_result=None,
                        freshness=None, execution=None,
                        extra_questions=questions)
    return questions


class TestValueTraceDiscoveryToPendingRead:
    def test_the_located_source_creates_a_selectable_content_read_action(
            self, lifecycle):
        """Step-2 assertion (captured planned=False state + the captured
        value-trace receipt): the located source produces a SELECTABLE
        content-read action — and the action carries the requested-value
        obligation so the content read can bind."""
        from core.task_lifecycle import (
            begin_retrieval_turn, next_unfinished_work)

        run_id, op_id = begin_retrieval_turn(
            lifecycle, {"id": "s1"}, "conv-chain",
            "chained required-source lookup: datasets (SLE24-16 Tennsmith)",
            "e1", items=["SLE24-16", "Tennsmith SLE24-16"],
            requested_fields=["price", "lead_time"])
        _settle_value_trace(lifecycle, run_id, op_id,
                            ["SLE24-16"], ["price", "lead_time"])
        work = next_unfinished_work(lifecycle.get_task(run_id))
        actions = [a for a in work["actions"]
                   if "Consolidated Price List 2019.xlsx"
                   in str(a.get("next_action") or "")]
        assert actions, (
            "the located source must create a selectable content-read "
            "action")
        act = actions[0]
        assert act.get("inputs", {}).get("requested_fields"), (
            "the content-read action must carry the requested-value "
            "obligation (inputs.requested_fields); a contract at the "
            "question's top level is dropped at normalization")

    def test_the_persisted_question_keeps_the_contract_after_normalization(
            self, lifecycle):
        """The captured first false condition: the spawner's
        requested_fields must survive ``_normalize_question`` — the
        persisted question (what the worker re-reads) carries them."""
        from core.task_lifecycle import begin_retrieval_turn

        run_id, op_id = begin_retrieval_turn(
            lifecycle, {"id": "s1"}, "conv-norm", "verify pricing", "e1",
            items=["SLE24-16"])
        _settle_value_trace(lifecycle, run_id, op_id,
                            ["SLE24-16"], ["price", "lead_time"])
        record = lifecycle.get_task(run_id)
        stored = [q for q in (record["task_revision"].get("unresolved") or [])
                  if q.get("status") == "open"]
        assert stored, "the pending read must persist"
        assert (stored[0].get("inputs") or {}).get("requested_fields"), (
            "the persisted inputs must carry the field contract")


class TestContentReadToTypedFindings:
    def test_in_turn_content_read_settles_typed_findings(self, lifecycle):
        """In-turn scheduling path: the content read's receipt converts
        through the EXISTING converter and settles on the operation
        record — subject/field/value/basis/source together."""
        from core.task_lifecycle import (
            begin_retrieval_turn, finish_retrieval_turn)
        from integrations.chat_orchestrator import (
            _findings_from_structured_result)

        run_id, op_id = begin_retrieval_turn(
            lifecycle, {"id": "s1"}, "conv-inturn", "verify pricing", "e1",
            items=["SLE24-16"], requested_fields=["price", "lead_time"])
        findings = _findings_from_structured_result(CONTENT_READ_META)
        assert findings, "the content read's receipt must convert"
        f = findings[0]
        assert f["field"] == "price"
        assert f["value"] == "8,984"
        assert (f.get("parsed") or {}).get("value") == 8984.0
        assert (f.get("parsed") or {}).get("basis") == "U.S. LIST"
        assert f["source"] == (
            "Consolidated Price List 2019.xlsx!Tennsmith !row101")
        finish_retrieval_turn(
            lifecycle, run_id, op_id, {}, "e1", True,
            execution={"invoked": True, "outcome": "read_succeeded",
                       "served_basis": "saved_copy", "failure_stage": None,
                       "findings": findings,
                       "items": {"SLE24-16": "matched"}})
        record = lifecycle.get_task(run_id)
        op = (record.get("operations") or [])[0]
        assert (op.get("execution") or {}).get("findings"), (
            "the in-turn content read must leave typed findings on the "
            "operation record")

    def test_deferred_content_read_executes_through_the_existing_worker(
            self, lifecycle, monkeypatch):
        """Insufficient budget: the read persists and the EXISTING worker
        (research_continuation executors + claims + settlement) executes
        it later — the row-context read binds the contract the action
        carries and settles typed findings."""
        import core.research_continuation as rc
        import core.sheet_dataset_service as sds
        import core.task_lifecycle as tlm
        from core.task_lifecycle import (
            begin_retrieval_turn, next_unfinished_work)

        run_id, op_id = begin_retrieval_turn(
            lifecycle, {"id": "s1"}, "conv-worker", "verify pricing", "e1",
            items=["SLE24-16"], requested_fields=["price", "lead_time"])
        _settle_value_trace(lifecycle, run_id, op_id,
                            ["SLE24-16"], ["price", "lead_time"])

        monkeypatch.setattr(
            sds, "find_all_occurrences_sync",
            lambda item, user_id, ws, file_name=None, max_matches=8, **kw: {
                "matches": [{"sheet": "Tennsmith ", "cell": "A101",
                             "column": "MODEL NO.", "value": "SLE24-16",
                             "formula": None, "file_name": file_name}]})
        monkeypatch.setattr(
            sds, "read_sheet_row_sync",
            lambda f, s, r, u, w: {
                "headers": list(TENNSMITH_ROW.keys()), "row": TENNSMITH_ROW,
                "source": {"file_name": f, "sheet_raw": s, "entry_id": "e1",
                           "parquet_mtime": 1.0}})
        monkeypatch.setattr(tlm, "resolve_unresolved_questions_fenced",
                            lambda *a, **k: True)

        async def _run():
            work = next_unfinished_work(lifecycle.get_task(run_id))
            acts = rc._read_actions(work.get("actions") or [])
            assert acts, "the pending read must reach the worker's actions"
            res = await rc._execute_document_read(
                lifecycle, run_id, "u1", "ws",
                "Consolidated Price List 2019.xlsx", ["SLE24-16"],
                item_identity_context="SLE24-16 Tennsmith",
                action_inputs=(acts[0].get("inputs") or {}))
            assert res["statuses"].get("SLE24-16") == "located", res
            work2 = next_unfinished_work(lifecycle.get_task(run_id))
            row_acts = [a for a in rc._read_actions(work2.get("actions") or [])
                        if a.get("intent") == "row_read"]
            assert row_acts, "the located source must spawn a row-read action"
            assert row_acts[0].get("requested_fields"), (
                "the content read must receive the field contract from the "
                "action's inputs")
            res2 = await rc._execute_row_read(
                lifecycle, run_id, "u1", "ws", row_acts[0],
                [row_acts[0].get("question_id")], agent_lessons=[])
            assert res2["statuses"].get("SLE24-16") == "matched", res2

        asyncio.run(_run())
        record = lifecycle.get_task(run_id)
        findings = [f for op in record.get("operations") or []
                    for f in ((op.get("execution") or {}).get("findings")
                              or [])]
        assert findings, (
            "the deferred content read must leave typed findings on the "
            "operation record")
        assert any(f.get("field") for f in findings)
        assert any(
            (f.get("parsed") or {}).get("value") is not None or f.get("raw")
            for f in findings), findings


class TestDurableReuseThroughTheDraftingAdapter:
    def test_fresh_reload_keeps_subject_field_value_basis_source_and_freshness(
            self, lifecycle):
        from core.task_lifecycle import (
            begin_retrieval_turn, finish_retrieval_turn)
        from integrations.chat_orchestrator import (
            _findings_from_structured_result)

        run_id, op_id = begin_retrieval_turn(
            lifecycle, {"id": "s1"}, "conv-reload", "verify pricing", "e1",
            items=["SLE24-16"], requested_fields=["price", "lead_time"])
        finish_retrieval_turn(
            lifecycle, run_id, op_id, {}, "e1", True,
            execution={"invoked": True, "outcome": "read_succeeded",
                       "served_basis": "saved_copy",
                       "freshness_status": "saved_copy_unverified",
                       "failure_stage": None,
                       "findings": _findings_from_structured_result(
                           CONTENT_READ_META),
                       "items": {"SLE24-16": "matched"}})

        # FRESH RELOAD through a second lifecycle instance over the same
        # store — then the drafting adapter.
        import integrations.chat_orchestrator as chat
        from types import SimpleNamespace
        from unittest.mock import patch

        fresh = _fresh(lifecycle)
        orch = chat.ChatOrchestrator.__new__(chat.ChatOrchestrator)
        orch.tenant_id = "t"
        with patch.object(chat, "_task_lifecycle_for", return_value=fresh):
            out = orch._canvas_job_findings(
                "u1", {"canvas_id": None}, {"id": "conv-reload"},
                "draft the quote", agent_id=None)
        assert out is not None, (
            "a job with durable findings must reach the drafting adapter")
        typed = out.get("typed_findings") or []
        assert typed, out
        f = typed[0]
        assert f.get("subject") == "SLE24-16"
        assert f.get("field") == "price"
        assert f.get("value") == 8984.0
        assert f.get("basis") == "U.S. LIST"
        assert f.get("source") == (
            "Consolidated Price List 2019.xlsx!Tennsmith !row101")
        assert f.get("operation_id")
        assert f.get("served_basis") == "saved_copy"
        assert f.get("freshness_status") == "saved_copy_unverified"


class TestGuardrails:
    def test_receiptless_targets_produce_no_verified_findings(self):
        """A structured receipt with no values is not evidence."""
        from integrations.chat_orchestrator import (
            _findings_from_structured_result)
        meta = {"structured_result": {"targets": [
            {"item": "SLE24-16", "identity": {"status": "none"},
             "field": {"status": "absent", "values": []}}]}}
        assert _findings_from_structured_result(meta) == []

    def test_discovery_alone_resolves_no_requested_value(self):
        """The value-trace coverage is discovery: the pending read it
        creates names the document to READ — it carries no value."""
        from integrations.chat_orchestrator import _value_trace_pending_reads
        qs = _value_trace_pending_reads(
            VALUE_TRACE_RECEIPT, requested_fields=["price"])
        assert qs and all("is carried by" in q["question"] for q in qs)
        assert all(q.get("kind") == "verification" for q in qs)
        assert not any(
            str(v).replace(",", "").replace(".", "").isdigit()
            for q in qs for v in q.get("inputs", {}).values()
            if isinstance(v, str))

    def test_multi_column_row_persists_candidates_not_a_chosen_price(self):
        """Ambiguity stays explicit: each surviving candidate carries its
        own column/basis — persistence never implies a chosen price."""
        from integrations.chat_orchestrator import (
            _findings_from_structured_result)
        meta = {"structured_result": {
            "source_identity": {"file_name": "Consolidated Price List "
                                            "2019.xlsx"},
            "requested_fields": ["price"],
            "targets": [{
                "item": "SLE24-16",
                "identity": {"status": "single", "candidates": [
                    {"ref": "Tennsmith !R101"}]},
                "field": {"status": "competing", "values": [
                    {"col": "C101", "basis": "U.S. LIST", "kind": "number",
                     "value": 8984.0, "display": "8,984"},
                    {"col": "E101", "basis": "CANADIAN COST",
                     "kind": "number", "value": 9450.0, "display": "9,450"}]},
            }]}}
        findings = _findings_from_structured_result(meta)
        assert len(findings) == 2, findings
        assert {f["column"] for f in findings} == {
            "U.S. LIST", "CANADIAN COST"}, (
            "every candidate keeps its own basis — no first-picking")

    def test_the_pre_read_receipt_subdict_yields_no_findings(self):
        """The captured false predicate, pinned: the search-receipt
        sub-dict carries no structured_result/storage_read keys, so the
        converter cannot read the content read's values from it."""
        from integrations.chat_orchestrator import (
            _findings_from_datasets_receipt, _findings_from_structured_result)
        receipt = VALUE_TRACE_RECEIPT["receipt"]
        assert _findings_from_structured_result(receipt) == []
        assert _findings_from_datasets_receipt(receipt) == []
