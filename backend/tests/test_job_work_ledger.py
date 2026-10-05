"""Job-work ledger tests — execution facts, unresolved questions,
continuation selection, canvas-scoped resume (2026-10-04 assignment).

Scratch-file sqlite via injected session_factory — never the live dev DB.
Item codes and questions are domain-free (M-1..M-3, generic sources):
the ledger must not know quotation vocabulary to be correct.
"""
import os
from unittest.mock import MagicMock

import types

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

os.environ.setdefault("TESTING", "1")

from core.models import GoalObjective, GoalRun, TaskOperationRecord
from core.goals.goal_run_service import GoalRunService
from core.goals.goal_service import GoalService
from core.task_lifecycle import (
    TaskLifecycle,
    TaskLifecycleError,
    add_unresolved_questions,
    begin_retrieval_turn,
    bump_question_attempts,
    derive_read_questions,
    finish_retrieval_turn,
    next_unfinished_work,
    normalize_execution_facts,
    open_unresolved_questions,
    record_read_outcome,
    resolve_unresolved_questions,
)


@pytest.fixture()
def lifecycle(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path}/job_work_ledger_test.db")
    for table in (GoalObjective.__table__, GoalRun.__table__,
                  TaskOperationRecord.__table__):
        table.create(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    runs = GoalRunService(workspace_id="ws_test", tenant_id="t_test",
                          session_factory=factory)
    goals = GoalService(workspace_id="ws_test", tenant_id="t_test",
                        session_factory=factory)
    return TaskLifecycle(runs, goals)


def _read_fixture():
    """One read's observed world: one ambiguous item, one absent item,
    one found item, and a refresh that failed at the source."""
    structured = {
        "targets": [
            {"item": "M-1", "identity": {"status": "multiple",
                                         "detail": "3 candidate rows"}},
            {"item": "M-2", "identity": {"status": "none"}},
            {"item": "M-3", "identity": {"status": "single"}},
        ],
        "attempt_id": "a1",
        "evidence_revision": "r1",
        "requested_items": ["M-1", "M-2", "M-3"],
    }
    freshness = {
        "status": "refresh_failed",
        "refresh_outcome": {"attempted": True, "stage": "source_refused",
                            "detail": "provider said no"},
    }
    return structured, freshness


class TestExecutionFacts:
    def test_saved_copy_success_is_not_a_failed_refresh(self):
        """The reviewer's dimension split: one turn can be BOTH a
        successful saved-copy read AND a failed refresh — only the pair
        of fields tells the truth."""
        facts = normalize_execution_facts({
            "invoked": True, "outcome": "read_succeeded",
            "served_basis": "saved_copy",
            "freshness_status": "refresh_failed",
            "failure_stage": "source_refused",
        })
        assert facts["outcome"] == "read_succeeded"
        assert facts["served_basis"] == "saved_copy"
        assert facts["freshness_status"] == "refresh_failed"
        assert facts["failure_stage"] == "source_refused"

    def test_not_dispatched_is_distinct_from_read_failed(self):
        not_run = normalize_execution_facts({"invoked": False})
        ran_failed = normalize_execution_facts(
            {"invoked": True, "outcome": "read_failed"})
        assert not_run["outcome"] == "not_dispatched"
        assert ran_failed["outcome"] == "read_failed"
        assert not_run["outcome"] != ran_failed["outcome"]

    def test_unknown_vocabulary_falls_back_along_invocation_only(self):
        facts = normalize_execution_facts(
            {"invoked": True, "outcome": "something novel"})
        assert facts["outcome"] == "read_failed"
        assert facts["raw_outcome"] == "something novel"
        assert normalize_execution_facts(
            {"invoked": False, "outcome": "weird"})["outcome"] == (
            "not_dispatched")

    def test_facts_attach_to_the_operation(self, lifecycle):
        session = {}
        run_id, op_id = begin_retrieval_turn(
            lifecycle, session, "conv-exec", "check the records", "ex-1",
            items=["M-1"])
        finish_retrieval_turn(
            lifecycle, run_id, op_id,
            {"requested_items": ["M-1"], "attempt_id": "a1"}, "ex-1", True,
            execution={"invoked": True, "outcome": "read_succeeded",
                       "served_basis": "saved_copy",
                       "items": {"M-1": "single"}})
        operation = next(
            op for op in lifecycle.get_task(run_id)["operations"]
            if op["operation_id"] == op_id)
        assert operation["execution"]["outcome"] == "read_succeeded"
        assert operation["execution"]["invoked"] is True
        assert operation["execution"]["items"] == {"M-1": "single"}


class TestUnresolvedQuestions:
    def test_add_then_open_then_resolved_stops_resurfacing(self, lifecycle):
        created = lifecycle.create_task("conv-q", "verify records")
        run_id = created["run_id"]
        added = add_unresolved_questions(lifecycle, run_id, [{
            "item": "M-1", "kind": "business_decision",
            "question": "which M-1 row is the right one",
            "evidence": "3 candidates matched",
        }])
        assert len(added) == 1
        assert open_unresolved_questions(lifecycle.get_task(run_id))
        settled = resolve_unresolved_questions(
            lifecycle, run_id, items=["M-1"],
            kinds=["business_decision"],
            resolution="owner picked row 268")
        assert len(settled) == 1
        assert open_unresolved_questions(lifecycle.get_task(run_id)) == []
        # The resolved entry stays on the revision for audit.
        entries = lifecycle.get_task(run_id)["task_revision"]["unresolved"]
        assert entries[0]["status"] == "resolved"
        assert entries[0]["resolution"] == "owner picked row 268"

    def test_duplicate_question_not_re_added(self, lifecycle):
        created = lifecycle.create_task("conv-dup", "verify records")
        run_id = created["run_id"]
        question = {"item": "M-2", "kind": "missing_evidence",
                    "question": "no source on file carries M-2",
                    "next_action": "search supplier correspondence"}
        assert len(add_unresolved_questions(lifecycle, run_id, [question])) == 1
        assert add_unresolved_questions(lifecycle, run_id, [question]) == []
        assert len(open_unresolved_questions(lifecycle.get_task(run_id))) == 1

    def test_executable_kinds_require_a_next_action(self, lifecycle):
        created = lifecycle.create_task("conv-kind", "verify records")
        with pytest.raises(TaskLifecycleError):
            add_unresolved_questions(lifecycle, created["run_id"], [{
                "item": "M-9", "kind": "verification",
                "question": "is the source current"}])

    def test_unknown_kind_rejected(self):
        with pytest.raises(TaskLifecycleError):
            add_unresolved_questions(MagicMock(), "run", [{
                "item": "M-9", "kind": "vibes", "question": "?",
                "next_action": "x"}])

    def test_resolution_text_required(self, lifecycle):
        created = lifecycle.create_task("conv-res", "verify records")
        run_id = created["run_id"]
        add_unresolved_questions(lifecycle, run_id, [{
            "item": "M-4", "kind": "verification",
            "question": "is the source current",
            "next_action": "retry"}])
        with pytest.raises(TaskLifecycleError):
            resolve_unresolved_questions(lifecycle, run_id, items=["M-4"],
                                         resolution="  ")


class TestDeriveSeparatesDimensions:
    """Correction #2: match status is not job completion. A 'single'
    match resolves ONLY missing-evidence; freshness resolves ONLY
    verification; a binding resolves ONLY the decision."""

    def test_full_dimension_matrix(self):
        structured, freshness = _read_fixture()
        derived = derive_read_questions(structured, freshness)
        kinds = {(q["item"], q["kind"]) for q in derived["questions"]}
        assert ("M-1", "business_decision") in kinds
        assert ("M-2", "missing_evidence") in kinds
        assert ("", "verification") in kinds
        assert ("M-3", "missing_evidence") not in kinds  # found
        resolutions = {(tuple(r["items"]), tuple(r["kinds"]))
                       for r in derived["resolutions"]}
        assert (("M-3",), ("missing_evidence",)) in resolutions
        # A failed refresh resolves nothing.
        assert not any("verification" in r["kinds"]
                       for r in derived["resolutions"])

    def test_single_match_does_not_resolve_decision_or_freshness(self):
        derived = derive_read_questions(
            {"targets": [{"item": "M-1",
                          "identity": {"status": "single"}}]},
            {"status": "refresh_failed"},
        )
        assert derived["questions"] == [{
            "item": "", "kind": "verification",
            "question": "current-source verification did not succeed",
            "evidence": "freshness verdict refresh_failed "
                        "(stage: unattributed)",
            "next_action": "retry live source verification",
        }]
        assert derived["resolutions"] == [
            {"items": ["M-1"], "kinds": ["missing_evidence"],
             "resolution": "found on file by a completed read"}]

    def test_binding_resolves_only_the_decision(self):
        derived = derive_read_questions(
            {"targets": [{"item": "M-1",
                          "identity": {"status": "multiple"}}]},
            {"status": "refreshed"},
            bindings=[{"item": "M-1", "sheet": "S", "row": 7}],
        )
        assert derived["questions"] == []
        resolution_kinds = {tuple(r["kinds"]) for r in derived["resolutions"]}
        assert ("business_decision",) in resolution_kinds
        assert ("verification",) in resolution_kinds

    def test_fresh_success_resolves_only_verification(self):
        derived = derive_read_questions(
            {"targets": [{"item": "M-2",
                          "identity": {"status": "none"}}]},
            {"status": "current"},
        )
        assert [q["kind"] for q in derived["questions"]] == [
            "missing_evidence"]
        assert [r["kinds"] for r in derived["resolutions"]] == [
            ["verification"]]


class TestNextUnfinishedWork:
    def test_classes_and_attempt_budget(self, lifecycle):
        created = lifecycle.create_task("conv-next", "verify records")
        run_id = created["run_id"]
        add_unresolved_questions(lifecycle, run_id, [
            {"item": "M-1", "kind": "business_decision",
             "question": "which M-1 row", "evidence": "ambiguous"},
            {"item": "M-2", "kind": "missing_evidence",
             "question": "no source carries M-2",
             "next_action": "search supplier correspondence for M-2"},
            {"item": "M-5", "kind": "verification",
             "question": "is the source current",
             "next_action": "retry live verification"},
        ])
        record = lifecycle.get_task(run_id)
        work = next_unfinished_work(record)
        assert [a["item"] for a in work["actions"]] == ["M-2", "M-5"]
        assert [d["item"] for d in work["owner_decisions"]] == ["M-1"]
        assert work["exhausted"] == []
        # Three attempts on M-2 exhaust it: reported, never re-selected.
        question_id = work["actions"][0]["question_id"]
        for _ in range(3):
            bump_question_attempts(lifecycle, run_id, [question_id])
        work = next_unfinished_work(lifecycle.get_task(run_id))
        assert [a["item"] for a in work["actions"]] == ["M-5"]
        assert [e["item"] for e in work["exhausted"]] == ["M-2"]
        # Owner decisions never become executable regardless of budget.
        assert all(d["kind"] == "business_decision"
                   for d in work["owner_decisions"])


class TestCanvasScopedResume:
    """Correction #4: cross-session continuation resolves through the
    canvas identity — never 'the latest conversation of the user'."""

    def test_canvas_match_and_non_match(self, lifecycle):
        session = {}
        run_id, _ = begin_retrieval_turn(
            lifecycle, session, "conv-canvas", "verify records", "ex-1",
            items=["M-1"], canvas_id="canvas-quo-1")
        found = lifecycle.find_active_task_for_canvas("canvas-quo-1")
        assert found is not None and found["run_id"] == run_id
        assert lifecycle.find_active_task_for_canvas("canvas-other") is None
        assert lifecycle.find_active_task_for_canvas("") is None

    def test_task_without_canvas_never_matches(self, lifecycle):
        begin_retrieval_turn(
            lifecycle, {}, "conv-plain", "verify records", "ex-1",
            items=["M-1"])
        assert lifecycle.find_active_task_for_canvas("canvas-quo-1") is None


class TestRecordReadOutcome:
    def test_settle_records_facts_questions_and_open_work(self, lifecycle):
        session = {}
        run_id, op_id = begin_retrieval_turn(
            lifecycle, session, "conv-rec", "verify records", "ex-1",
            items=["M-1", "M-2", "M-3"])
        structured, freshness = _read_fixture()
        finish_retrieval_turn(
            lifecycle, run_id, op_id, structured, "ex-1", True)
        work = record_read_outcome(
            lifecycle, run_id, op_id,
            structured_result=structured, freshness=freshness,
            execution={"invoked": True, "outcome": "read_succeeded",
                       "served_basis": "saved_copy",
                       "freshness_status": "refresh_failed",
                       "failure_stage": "source_refused",
                       "items": {"M-1": "multiple", "M-2": "none",
                                 "M-3": "single"}})
        kinds = {(q.get("item"), q["kind"])
                 for q in open_unresolved_questions(
                     lifecycle.get_task(run_id))}
        assert ("M-1", "business_decision") in kinds
        assert ("M-2", "missing_evidence") in kinds
        assert ("", "verification") in kinds
        assert work["actions"], "the verification question is executable"
        operation = next(
            op for op in lifecycle.get_task(run_id)["operations"]
            if op["operation_id"] == op_id)
        assert operation["execution"]["served_basis"] == "saved_copy"
        assert operation["execution"]["failure_stage"] == "source_refused"

    def test_later_read_resolves_what_it_settles(self, lifecycle):
        session = {}
        run_id, op_id = begin_retrieval_turn(
            lifecycle, session, "conv-rec2", "verify records", "ex-1",
            items=["M-1", "M-2"])
        structured, freshness = _read_fixture()
        record_read_outcome(lifecycle, run_id, op_id,
                            structured_result=structured,
                            freshness=freshness)
        # Second read: M-2 found, M-1 owner-bound, refresh succeeded.
        record_read_outcome(
            lifecycle, run_id, op_id,
            structured_result={"targets": [
                {"item": "M-1", "identity": {"status": "multiple"}},
                {"item": "M-2", "identity": {"status": "single"}}]},
            freshness={"status": "refreshed"},
            bindings=[{"item": "M-1", "sheet": "S", "row": 268}])
        assert open_unresolved_questions(lifecycle.get_task(run_id)) == []
        work = next_unfinished_work(lifecycle.get_task(run_id))
        assert work["actions"] == [] and work["owner_decisions"] == []


class TestPlanningProvenanceAndDeniedEdits:
    """Reviewer correction 2 (recovered attempts) and correction 4
    (denied edits recorded, gate untouched)."""

    def test_recovered_attempt_is_not_not_dispatched(self):
        """A planner failure the fallback machinery recovered, followed by
        a successful tool execution, records as a SUCCESS with its
        planning provenance — attempt history, never a final
        not_dispatched verdict."""
        facts = normalize_execution_facts({
            "invoked": True, "outcome": "search_succeeded",
            "served_basis": "live",
            "planning": {"source": "service_repair", "recovered": True},
        })
        assert facts["outcome"] == "search_succeeded"
        assert facts["invoked"] is True
        assert facts["planning"] == {
            "source": "service_repair", "recovered": True}
        assert facts["outcome"] != "not_dispatched"

    def test_planning_provenance_clamped(self):
        facts = normalize_execution_facts({
            "invoked": True, "outcome": "read_succeeded",
            "planning": "nonsense",
        })
        assert facts["planning"] is None

    def test_denied_edit_records_without_weakening_the_gate(
            self, lifecycle):
        """An attempted edit the scope gate refused: the operation exists,
        ends cancelled (the effect did not happen), and carries the denial
        reason — zero writes, but 'nothing was attempted' is no longer the
        recorded story."""
        from core.task_lifecycle import record_denied_edit_attempt

        created = lifecycle.create_task("conv-denied", "prepare the draft")
        run_id = created["run_id"]
        op = record_denied_edit_attempt(
            lifecycle, run_id, "prepare the email draft",
            "scope validator refused edit for this request")
        assert op is not None
        operation = next(
            o for o in lifecycle.get_task(run_id)["operations"]
            if o["operation_id"] == op["operation_id"])
        assert operation["status"] == "cancelled"
        assert operation["operation_type"] == "edit"
        assert "refused" in operation["denied"]["reason"]
        assert record_denied_edit_attempt(lifecycle, None, "x", "y") is None


class TestPlannerPlanningMeta:
    """The plan-level provenance markers plan_tool_use attaches."""

    @pytest.mark.asyncio
    async def test_service_repair_marks_recovered(self, monkeypatch):
        from core import chat_tool_planner as ctp
        from core.chat_tool_planner import ToolPlan, plan_tool_use

        calls = {"n": 0}

        async def fake_structured(llm_service, *, prompt, response_model,
                                  system_instruction, **kw):
            calls["n"] += 1
            if calls["n"] == 1:
                # First pass: invalid — a service not in the catalog.
                return ToolPlan(use_tool=True, service="no-such-svc",
                                intent="search", query="widget W-1 price")
            # Repair pass: valid plan.
            return ToolPlan(use_tool=True, service="memory",
                            intent="search", query="widget W-1 price")

        monkeypatch.setattr(
            "core.llm.pinned_planning.pinned_structured_call",
            fake_structured)
        plan = await plan_tool_use(
            "check the widget W-1 price", [], "u1", object())
        assert plan is not None and plan.use_tool
        meta = plan._result_meta.get("planning") or {}
        assert meta.get("source") == "service_repair"
        assert meta.get("recovered") is True

    @pytest.mark.asyncio
    async def test_first_pass_success_not_recovered(self, monkeypatch):
        from core.chat_tool_planner import ToolPlan, plan_tool_use

        async def fake_structured(llm_service, *, prompt, response_model,
                                  system_instruction, **kw):
            return ToolPlan(use_tool=True, service="memory",
                            intent="search", query="widget W-1")

        monkeypatch.setattr(
            "core.llm.pinned_planning.pinned_structured_call",
            fake_structured)
        plan = await plan_tool_use(
            "check the widget W-1 price", [], "u1", object())
        meta = plan._result_meta.get("planning") or {}
        assert meta.get("source") == "structured"
        assert meta.get("recovered") is False


class TestInspectionSurface:
    """The 2026-10-04 audit request: the Milestone-A gate requires
    inspecting durable task state, and until now no surface exposed it
    (history drops response data; settle arms logged failures only)."""

    def test_snapshot_projection(self, lifecycle):
        from core.task_lifecycle import task_snapshot

        session = {}
        run_id, op_id = begin_retrieval_turn(
            lifecycle, session, "conv-snap", "verify records", "ex-1",
            items=["M-1", "M-2"], canvas_id="canvas-snap")
        structured, freshness = _read_fixture()
        finish_retrieval_turn(
            lifecycle, run_id, op_id, structured, "ex-1", True,
            execution={"invoked": True, "outcome": "read_succeeded",
                       "served_basis": "saved_copy"})
        record_read_outcome(
            lifecycle, run_id, op_id,
            structured_result=structured, freshness=freshness)
        record = lifecycle.get_task(run_id)
        snap = task_snapshot(record)
        assert snap["run_id"] == run_id
        assert snap["conversation_id"] == "conv-snap"
        assert snap["canvas_id"] == "canvas-snap"
        # finish_retrieval_turn reconciles entities to the observed
        # item set (the fixture reads three items).
        assert snap["entities"] == ["M-1", "M-2", "M-3"]
        assert snap["open_questions"], "open questions visible"
        assert snap["next_work"]["actions"], "next work visible"
        op = snap["operations"][0]
        assert op["execution"]["outcome"] == "read_succeeded"
        assert op["execution"]["served_basis"] == "saved_copy"

    def test_snapshot_empty_record(self):
        from core.task_lifecycle import task_snapshot

        assert task_snapshot({}) == {"task": None}
        assert task_snapshot(None) == {"task": None}

    def test_settle_logs_one_info_line(self, lifecycle, caplog):
        """The log is the only always-on engagement signal — one INFO
        per settle, identifiers and counts only."""
        import logging as _logging

        session = {}
        run_id, op_id = begin_retrieval_turn(
            lifecycle, session, "conv-log", "verify records", "ex-1",
            items=["M-1"])
        with caplog.at_level(_logging.INFO, logger="core.task_lifecycle"):
            record_read_outcome(
                lifecycle, run_id, op_id,
                structured_result={"targets": [
                    {"item": "M-1", "identity": {"status": "none"}}]},
                freshness=None)
        line = [r for r in caplog.records
                if "job-work-ledger] settled" in r.getMessage()]
        assert len(line) == 1
        assert f"run={str(run_id)[:8]}" in line[0].getMessage()
        assert "open(actions=1" in line[0].getMessage()


class TestExecutionFactsSurviveReload:
    """Round 36 reviewer correction 2: the execution-facts attach lived
    below finish_retrieval_turn's `if not complete: return` early return —
    every failed / chained / incomplete settle persisted an operation row
    with NO execution facts. Provenance is completeness-neutral."""

    def test_incomplete_settle_persists_execution_facts(self, lifecycle):
        from core.task_lifecycle import (
            begin_retrieval_turn, finish_retrieval_turn, record_read_outcome)

        run_id, op1 = begin_retrieval_turn(
            lifecycle, {"id": "s1"}, "conv-facts", "primary lookup", "e1")
        finish_retrieval_turn(
            lifecycle, run_id, op1, {}, "e1", False,
            execution={"invoked": True,
                       "outcome": "search_returned_no_receipt",
                       "served_basis": "live", "failure_stage": None,
                       "planning": {"source": "structured",
                                    "recovered": False},
                       "items": {"SLE24-16": ""}})
        record_read_outcome(lifecycle, run_id, op1, structured_result=None,
                            freshness=None, execution=None)

        # A chained operation on the SAME run, also incomplete.
        _, op2 = begin_retrieval_turn(
            lifecycle, {"id": "s1"}, "conv-facts",
            "chained lookup: datasets", "e1")
        finish_retrieval_turn(
            lifecycle, run_id, op2, {}, "e1", False,
            execution={"invoked": True, "outcome": "search_succeeded",
                       "served_basis": "live", "failure_stage": None,
                       "planning": {}, "items": {"U-22": ""}})

        # RELOAD from durable storage — the operation rows must carry
        # their facts, not just in-memory state.
        rec = lifecycle.get_task(run_id)
        by_id = {op["operation_id"]: op for op in rec["operations"]}
        for op_id in (op1, op2):
            facts = by_id[op_id].get("execution")
            assert facts and facts.get("outcome"), (
                "an operation row without its execution facts does not "
                "satisfy the ledger requirement")
        assert by_id[op1]["execution"]["outcome"] == \
            "search_returned_no_receipt"
        assert by_id[op2]["execution"]["outcome"] == "search_succeeded"


class TestValueTraceCoverageCreatesPendingReads:
    """Round 42: the deterministic receipt-to-action failure. A value_trace
    receipt locating a workbook produced NO pending action — the per-item
    questions were gated behind settle completeness, so discovery was
    treated as completion. Fixture: the live cont14 receipt shape."""

    RECEIPT = {
        "dispatched": True, "retrieved": True, "bounded_absence": False,
        "receipt": {
            "structured_keys": [], "searched_threads": 6,
            "source_observations": 0, "read_outcomes": 3,
            "datasets_search": {},
            "value_trace_coverage": {
                "Manual Flanger": ["Consolidated Price List 2019.xlsx"],
                "TK 1624": ["Consolidated Price List 2019.xlsx"],
                "GSL48-16": ["Consolidated Price List 2019.xlsx"]},
            "coverage_items": []}}

    def test_coverage_creates_pending_reads_selected_then_resolved(
            self, lifecycle):
        from core.task_lifecycle import (
            begin_retrieval_turn, finish_retrieval_turn,
            next_unfinished_work, record_read_outcome,
            resolve_unresolved_questions)
        from integrations.chat_orchestrator import _value_trace_pending_reads

        questions = _value_trace_pending_reads(self.RECEIPT)
        assert len(questions) == 3, "one pending read per covered item"
        assert all(
            "read Consolidated Price List 2019.xlsx" in q["next_action"]
            for q in questions), "the located workbook is the read input"

        run_id, op = begin_retrieval_turn(
            lifecycle, {"id": "s1"}, "conv-vt", "verify pricing", "e1")
        finish_retrieval_turn(
            lifecycle, run_id, op,
            {"requested_items": ["Manual Flanger"]}, "e1", False,
            execution={"invoked": True, "outcome": "search_succeeded",
                       "served_basis": "live",
                       "items": {"Manual Flanger": ""}})
        record_read_outcome(
            lifecycle, run_id, op, structured_result=None, freshness=None,
            execution=None, extra_questions=questions)

        work = next_unfinished_work(lifecycle.get_task(run_id))
        assert any(
            "Consolidated Price List 2019.xlsx" in (a.get("next_action") or "")
            for a in work["actions"]), (
            "the discovered workbook must produce a pending read action")

        # Repeated receipt: no duplicate actions.
        record_read_outcome(
            lifecycle, run_id, op, structured_result=None, freshness=None,
            execution=None, extra_questions=questions)
        work2 = next_unfinished_work(lifecycle.get_task(run_id))
        flanger_actions = [
            a for a in work2["actions"] if "Flanger" in str(a)]
        assert len(flanger_actions) == 1

        # The targeted read executes: evidence covers the item, the action
        # must stop being selected.
        _, op2 = begin_retrieval_turn(
            lifecycle, {"id": "s1"}, "conv-vt",
            "read Consolidated Price List 2019.xlsx for Manual Flanger",
            "e2")
        finish_retrieval_turn(
            lifecycle, run_id, op2,
            {"requested_items": ["Manual Flanger"]}, "e2", True,
            execution={"invoked": True, "outcome": "read_succeeded",
                       "served_basis": "live",
                       "items": {"Manual Flanger": "confirmed"}})
        record_read_outcome(
            lifecycle, run_id, op2,
            structured_result={"requested_items": ["Manual Flanger"],
                               "targets": [{"item": "Manual Flanger",
                                            "identity": {
                                                "status": "confirmed"}}]},
            freshness=None, execution=None)
        resolve_unresolved_questions(
            lifecycle, run_id, items=["Manual Flanger"],
            resolution={"how": "workbook cell read",
                        "detail": "Consolidated Price List 2019.xlsx"})
        work3 = next_unfinished_work(lifecycle.get_task(run_id))
        assert not any(
            "Flanger" in str(a) for a in work3["actions"]), (
            "a completed action must not be selected again")

    def test_irrelevant_discovery_creates_no_false_obligation(self):
        from integrations.chat_orchestrator import _value_trace_pending_reads

        assert _value_trace_pending_reads({
            "dispatched": True, "retrieved": False,
            "bounded_absence": False,
            "receipt": {"value_trace_coverage": {}}}) == []
        assert _value_trace_pending_reads(None) == []


class TestValueTraceProductionHandoff:
    """Round 43: the regression runs UPSTREAM — the real
    execute_tool_plan value_trace branch produces the receipt, which is
    carried through the production question derivation into settlement.
    No manual receipt attachment at the point under test."""

    @pytest.mark.asyncio
    async def test_real_value_trace_execution_creates_pending_reads(
            self, lifecycle, monkeypatch):
        import asyncio

        import integrations.chat_orchestrator as orch
        from core.task_lifecycle import (
            begin_retrieval_turn, finish_retrieval_turn,
            next_unfinished_work, record_read_outcome)

        def fake_trace(items, **kw):
            # The real executor calls this on a thread with the real
            # signature; the fixture supplies the per-item bindings.
            return {"Manual Flanger": ["Consolidated Price List 2019.xlsx"],
                    "TK 1624": ["Consolidated Price List 2019.xlsx"]}

        monkeypatch.setattr(
            "core.value_provenance.trace_items_across_catalog", fake_trace)

        from core.chat_tool_planner import ToolPlan, execute_tool_plan

        plan = ToolPlan(use_tool=True, service="datasets",
                        intent="value_trace",
                        query="Manual Flanger, TK 1624")
        block = await asyncio.wait_for(
            execute_tool_plan(plan, "u1", tenant_id="t1",
                              context={"history": []},
                              llm_service=None),
            timeout=30)

        # The receipt lives on the plan the executor returned — the
        # production handoff, not a manual attachment.
        questions = orch._value_trace_pending_reads(
            orch._search_execution_receipt(plan, block))
        assert len(questions) == 2
        assert all("Consolidated Price List 2019.xlsx" in
                   q["next_action"] for q in questions)

        run_id, op = begin_retrieval_turn(
            lifecycle, {"id": "s1"}, "conv-handoff", "verify pricing", "e1")
        finish_retrieval_turn(
            lifecycle, run_id, op, {}, "e1", False,
            execution={"invoked": True, "outcome": "search_succeeded",
                       "served_basis": "live", "items": {}})
        record_read_outcome(
            lifecycle, run_id, op, structured_result=None, freshness=None,
            execution=None, extra_questions=questions)
        work = next_unfinished_work(lifecycle.get_task(run_id))
        assert any("read Consolidated Price List 2019.xlsx" in
                   (a.get("next_action") or "") for a in work["actions"])

    def test_plan_absent_execution_settles_from_blackboard_meta(
            self, lifecycle):
        """The receipt belongs to the EXECUTION: a reused/plan-absent
        settlement reads the blackboard's recorded result meta — the
        production fallback installed at the seam."""
        from core.task_lifecycle import (
            begin_retrieval_turn, next_unfinished_work, record_read_outcome)
        from integrations.chat_orchestrator import (
            _search_execution_receipt, _value_trace_pending_reads)

        # The blackboard the singleflight arm records (execution-bound).
        blackboard = {"primary_result_meta": {"value_trace": {
            "Manual Flanger": ["Consolidated Price List 2019.xlsx"]}}}
        # No plan object survives — the receipt comes from the meta.
        receipt = _search_execution_receipt(None, "prose block")
        questions = _value_trace_pending_reads(receipt)
        # The plan-absent receipt carries NO value_trace (it was on the
        # original plan) — the blackboard meta is the settlement source:
        meta = blackboard["primary_result_meta"]
        receipt2 = _search_execution_receipt(
            types.SimpleNamespace(_result_meta=meta), "prose block")
        questions2 = _value_trace_pending_reads(receipt2)
        assert len(questions2) == 1
        assert "Manual Flanger" in questions2[0]["item"]

        run_id, op = begin_retrieval_turn(
            lifecycle, {"id": "s1"}, "conv-absent", "verify pricing", "e1")
        record_read_outcome(
            lifecycle, run_id, op, structured_result=None, freshness=None,
            execution=None, extra_questions=questions2)
        work = next_unfinished_work(lifecycle.get_task(run_id))
        assert any("read Consolidated Price List 2019.xlsx" in
                   (a.get("next_action") or "") for a in work["actions"])

    def test_migration_runs_on_settle_without_new_questions(self, lifecycle):
        """Round 43 live finding: the migration lived inside
        add_unresolved_questions — a settle with no derived questions
        never ran it, leaving broken-era exhaustion unrepairable exactly
        where no fresh evidence existed. The migration is now invoked by
        record_read_outcome itself."""
        from core.task_lifecycle import (
            UNRESOLVED_ATTEMPT_CAP, begin_retrieval_turn, next_unfinished_work,
            record_read_outcome)
        from integrations.chat_orchestrator import (
            _value_trace_pending_reads)

        run_id, op = begin_retrieval_turn(
            lifecycle, {"id": "s1"}, "conv-mig", "verify pricing", "e1")
        qs = _value_trace_pending_reads({
            "receipt": {"value_trace_coverage": {
                "Manual Flanger": [
                    "Consolidated Price List 2019.xlsx"]}}})
        record_read_outcome(
            lifecycle, run_id, op, structured_result=None, freshness=None,
            execution=None, extra_questions=qs)
        # Age the question past the cap WITHOUT new evidence (the
        # broken-loop era shape).
        from core.task_lifecycle import add_unresolved_questions
        add_unresolved_questions(lifecycle, run_id, [], source_operation=None)
        rec = lifecycle.get_task(run_id)
        bump = [{"question_id": q["question_id"],
                 "increment": UNRESOLVED_ATTEMPT_CAP}
                for q in rec["task_revision"].get("unresolved") or []]
        lifecycle.apply_transition(run_id, {
            "kind": "record_unresolved",
            "requested_change": "age to exhausted",
            "attempts": bump,
        })
        work = next_unfinished_work(lifecycle.get_task(run_id))
        assert work["exhausted"], "precondition: question exhausted"

        # A settle with NO new questions still repairs the budget.
        record_read_outcome(
            lifecycle, run_id, op, structured_result=None, freshness=None,
            execution=None, extra_questions=None)
        work2 = next_unfinished_work(lifecycle.get_task(run_id))
        assert not work2["exhausted"], (
            "the migration must run on every settle, not only when fresh "
            "questions are derived")
        assert any("Consolidated Price List 2019.xlsx" in
                   (a.get("next_action") or "") for a in work2["actions"])

    def test_reuse_settle_derives_pending_reads_from_blackboard(self,
                                                                 lifecycle):
        """Round 45 traced disappearance point: cont19/20's value_trace ran
        in the canvas-edit leg and settled ONLY via the singleflight arm —
        which never derived questions. The reuse settle now derives the
        pending reads from the blackboard's ORIGINAL receipt."""
        from core.task_lifecycle import (
            begin_retrieval_turn, next_unfinished_work, record_read_outcome)
        from integrations.chat_orchestrator import (
            _search_execution_receipt, _value_trace_pending_reads)

        # The blackboard exactly as the singleflight arm records it.
        original_plan = types.SimpleNamespace(_result_meta={
            "value_trace": {"Manual Flanger": [
                "Consolidated Price List 2019.xlsx"]}})
        shared_tool_state = {
            "primary_service": "datasets",
            "primary_receipt": _search_execution_receipt(
                original_plan, "prose block"),
            "primary_result_meta": {"value_trace": {
                "Manual Flanger": ["Consolidated Price List 2019.xlsx"]}},
        }
        # The reuse settle's derivation, as wired in production.
        questions = _value_trace_pending_reads(
            shared_tool_state.get("primary_receipt"))
        assert len(questions) == 1
        assert "read Consolidated Price List 2019.xlsx" in \
            questions[0]["next_action"]

        run_id, op = begin_retrieval_turn(
            lifecycle, {"id": "s1"}, "conv-reuse", "verify pricing", "e1")
        record_read_outcome(
            lifecycle, run_id, op, structured_result=None, freshness=None,
            execution=None, extra_questions=questions)
        work = next_unfinished_work(lifecycle.get_task(run_id))
        assert any("read Consolidated Price List 2019.xlsx" in
                   (a.get("next_action") or "") for a in work["actions"])

        # SOURCE-SHAPE: the reuse settle reads the blackboard receipt.
        orch_src = open("integrations/chat_orchestrator.py").read()
        assert 'shared_tool_state.get(\n                                                "primary_receipt")' \
            in orch_src

    def test_migration_is_one_time_and_retry_cap_holds(self, lifecycle):
        """Round 45: the migration must not defeat the retry cap.
        get_task does not surface decision_log — the original done-marker
        read an always-empty list, so the migration would have re-applied
        on EVERY settle once a question hit the cap. The marker now lives
        in the task revision: repeated settles, a restart (fresh
        TaskLifecycle on the same store), and identical rediscovery all
        leave a normally exhausted question EXHAUSTED."""
        from core.task_lifecycle import (
            UNRESOLVED_ATTEMPT_CAP, TaskLifecycle, begin_retrieval_turn,
            migrate_attempt_budgets, next_unfinished_work,
            record_read_outcome)
        from integrations.chat_orchestrator import (
            _value_trace_pending_reads)

        run_id, op = begin_retrieval_turn(
            lifecycle, {"id": "s1"}, "conv-cap", "verify pricing", "e1")
        qs = _value_trace_pending_reads({
            "receipt": {"value_trace_coverage": {
                "Manual Flanger": [
                    "Consolidated Price List 2019.xlsx"]}}})
        record_read_outcome(
            lifecycle, run_id, op, structured_result=None, freshness=None,
            execution=None, extra_questions=qs)
        rec = lifecycle.get_task(run_id)
        qid = (rec["task_revision"]["unresolved"])[0]["question_id"]
        lifecycle.apply_transition(run_id, {
            "kind": "record_unresolved", "requested_change": "age",
            "attempts": [{"question_id": qid,
                          "set": UNRESOLVED_ATTEMPT_CAP}]})

        # First repair settle: migration resets once and MARKS.
        record_read_outcome(
            lifecycle, run_id, op, structured_result=None, freshness=None,
            execution=None, extra_questions=None)
        w1 = next_unfinished_work(lifecycle.get_task(run_id))
        assert not w1["exhausted"], "one-time repair fires"
        assert (lifecycle.get_task(run_id)["task_revision"]
                .get("attempt_budget_migrated")), "marker is durable"

        # Age to cap again — a NORMALLY exhausted question.
        lifecycle.apply_transition(run_id, {
            "kind": "record_unresolved", "requested_change": "age",
            "attempts": [{"question_id": qid,
                          "set": UNRESOLVED_ATTEMPT_CAP}]})

        # Repeated settles: no second reset.
        for _ in range(3):
            record_read_outcome(
                lifecycle, run_id, op, structured_result=None,
                freshness=None, execution=None, extra_questions=None)
        w2 = next_unfinished_work(lifecycle.get_task(run_id))
        assert w2["exhausted"], (
            "a normally exhausted question stays exhausted — the "
            "migration must not run twice")

        # Identical rediscovery (same next_action) replenishes nothing.
        record_read_outcome(
            lifecycle, run_id, op, structured_result=None, freshness=None,
            execution=None, extra_questions=qs)
        w3 = next_unfinished_work(lifecycle.get_task(run_id))
        assert w3["exhausted"], (
            "identical evidence does not replenish the budget")

        # Restart: a fresh lifecycle over the same store sees the marker.
        restarted = TaskLifecycle(lifecycle.runs, lifecycle.goals)
        assert migrate_attempt_budgets(
            restarted, run_id,
            record=restarted.get_task(run_id)) == 0, (
            "the marker survives restart; no third reset")

    def test_read_succeeded_retires_the_targeted_question(self, lifecycle):
        """Round 45 completion rule: an open targeted-read question whose
        item receives an explicit status from a read_succeeded settle is
        RESOLVED (retired) — search success resolves nothing."""
        from core.task_lifecycle import (
            begin_retrieval_turn, finish_retrieval_turn,
            next_unfinished_work, record_read_outcome)
        from integrations.chat_orchestrator import (
            _value_trace_pending_reads)

        run_id, op = begin_retrieval_turn(
            lifecycle, {"id": "s1"}, "conv-retire", "verify pricing", "e1")
        record_read_outcome(
            lifecycle, run_id, op, structured_result=None, freshness=None,
            execution=None,
            extra_questions=_value_trace_pending_reads({
                "receipt": {"value_trace_coverage": {
                    "Manual Flanger": [
                        "Consolidated Price List 2019.xlsx"]}}}))
        work = next_unfinished_work(lifecycle.get_task(run_id))
        assert any("Flanger" in str(a) for a in work["actions"])

        _, op2 = begin_retrieval_turn(
            lifecycle, {"id": "s1"}, "conv-retire",
            "read Consolidated Price List 2019.xlsx for Manual Flanger",
            "e2")
        finish_retrieval_turn(
            lifecycle, run_id, op2, {}, "e2", True,
            execution={"invoked": True, "outcome": "read_succeeded",
                       "served_basis": "live",
                       "items": {"Manual Flanger": "single"}})
        record_read_outcome(
            lifecycle, run_id, op2, structured_result=None, freshness=None,
            execution={"invoked": True, "outcome": "read_succeeded",
                       "served_basis": "live",
                       "items": {"Manual Flanger": "single"}})
        work2 = next_unfinished_work(lifecycle.get_task(run_id))
        assert not any("Flanger" in str(a) for a in work2["actions"]), (
            "the completed targeted read retires its action")
        # A SEARCH success retires nothing (create the question first).
        record_read_outcome(
            lifecycle, run_id, op, structured_result=None, freshness=None,
            execution=None,
            extra_questions=[{
                "item": "TK 1624", "kind": "verification",
                "question": "TK 1624 is carried by X — not yet read",
                "evidence": "value_trace coverage",
                "next_action": "read X for TK 1624"}])
        _, op3 = begin_retrieval_turn(
            lifecycle, {"id": "s1"}, "conv-retire", "search", "e3")
        record_read_outcome(
            lifecycle, run_id, op3, structured_result=None, freshness=None,
            execution={"invoked": True, "outcome": "search_succeeded",
                       "served_basis": "live",
                       "items": {"TK 1624": ""}})
        work3 = next_unfinished_work(lifecycle.get_task(run_id))
        assert any("TK 1624" in str(a) for a in work3["actions"]), (
            "search success does not retire")

    def test_saved_copy_resolution_spawns_freshness_obligation(
            self, lifecycle):
        """Round 48: freshness is a DISTINCT blocked obligation, not
        wording on a completed read."""
        from core.task_lifecycle import (
            begin_retrieval_turn, next_unfinished_work, record_read_outcome)

        run_id, op = begin_retrieval_turn(
            lifecycle, {"id": "s1"}, "conv-fresh", "verify pricing", "e1")
        _, op2 = begin_retrieval_turn(
            lifecycle, {"id": "s1"}, "conv-fresh", "read workbook", "e2")
        record_read_outcome(
            lifecycle, run_id, op2, structured_result=None, freshness=None,
            execution={"invoked": True, "outcome": "read_succeeded",
                       "served_basis": "saved_copy",
                       "items": {"Manual Flanger": "single"}})
        w = next_unfinished_work(lifecycle.get_task(run_id))
        assert any(
            "freshness" in str(a.get("question") or "").lower()
            for a in w["actions"]), (
            "the saved-copy read leaves a selectable freshness obligation")

    def test_ambiguous_containment_resolves_neither(self, lifecycle):
        """Round 48: two question items containment-matching the same read
        key are AMBIGUOUS — neither resolves."""
        from core.task_lifecycle import (
            begin_retrieval_turn, next_unfinished_work, record_read_outcome)

        run_id, op = begin_retrieval_turn(
            lifecycle, {"id": "s1"}, "conv-amb", "verify pricing", "e1")
        record_read_outcome(
            lifecycle, run_id, op, structured_result=None, freshness=None,
            execution=None, extra_questions=[
                {"item": "TK 1624", "kind": "verification",
                 "question": "TK 1624 not yet read",
                 "evidence": "value_trace",
                 "next_action": "read X for TK 1624"},
                {"item": "1624 A", "kind": "verification",
                 "question": "1624 A not yet read",
                 "evidence": "value_trace",
                 "next_action": "read X for 1624 A"}])
        _, op2 = begin_retrieval_turn(
            lifecycle, {"id": "s1"}, "conv-amb", "read workbook", "e2")
        record_read_outcome(
            lifecycle, run_id, op2, structured_result=None, freshness=None,
            execution={"invoked": True, "outcome": "read_succeeded",
                       "served_basis": "saved_copy",
                       "items": {"1624": "single"}})
        w = next_unfinished_work(lifecycle.get_task(run_id))
        items_open = [str(a.get("item")) for a in w["actions"]]
        assert "TK 1624" in items_open and "1624 A" in items_open, (
            "ambiguous candidates resolve neither")


class TestJobScopeInitialization:
    """Round 50: the accepted job initializes BEFORE planning — the
    user's REQUEST establishes which canvas items are in scope; the
    canvas supplies candidates. Same persisted set feeds seam, chain and
    read loop."""

    CANVAS = {"canvas_id": "c1", "content": {
        "rows": [
            {"item": "Roper Whitney No. 381", "price": "$2,902.00"},
            {"item": "Linmac U-22", "price": "$1,777.00"},
            {"item": "Manual Flanger", "price": "$1,609.00"},
            {"item": "Tennsmith SLE24-16", "price": "$8,880.00"}]}}

    def _scope(self, message, canvas=None, current=None):
        from integrations.chat_orchestrator import _job_scope_items
        return _job_scope_items(message, canvas, current or [])

    def test_message_named_items_win(self):
        items, origin = self._scope(
            "check only the Manual Flanger price", self.CANVAS,
            current=["Manual Flanger"])
        assert items == ["Manual Flanger"] and origin == "message"

    def test_whole_quotation_request_resolves_canvas_items(self):
        items, origin = self._scope(
            "verify whether pricing on this quote needs updating",
            self.CANVAS)
        assert items, "quotation-scoped request yields the canvas items"
        assert origin in ("canvas-whole", "canvas-contrast", "canvas")

    def test_other_machinery_resolves_the_remainder(self):
        items, origin = self._scope(
            "check the other machinery and verify pricing",
            self.CANVAS)
        assert items, "'other' on a fresh job = the not-yet-covered set"
        assert "Manual Flanger" in " ".join(items) or len(items) >= 3

    def test_missing_or_ambiguous_is_explicitly_unresolved(self):
        items, origin = self._scope("check the other machinery", None)
        assert items == [] and origin == "unresolved"
        items2, origin2 = self._scope(
            "check things", {"canvas_id": "c", "content": {}})
        assert items2 == [] and origin2 == "unresolved"


class TestFreshnessSuccessorCannotLoop:
    """Round 50 reviewer check 4: repeated saved-copy reads must not
    duplicate freshness questions; the freshness action never rereads
    the saved copy; failure stays recorded."""

    def test_repeated_saved_copy_reads_do_not_duplicate_freshness(
            self, lifecycle):
        from core.task_lifecycle import (
            begin_retrieval_turn, next_unfinished_work,
            record_read_outcome)

        run_id, _ = begin_retrieval_turn(
            lifecycle, {"id": "s1"}, "conv-f2", "verify", "e1")
        for _ in range(3):
            _, op = begin_retrieval_turn(
                lifecycle, {"id": "s1"}, "conv-f2", "read workbook", "e2")
            record_read_outcome(
                lifecycle, run_id, op, structured_result=None,
                freshness=None,
                execution={"invoked": True, "outcome": "read_succeeded",
                           "served_basis": "saved_copy",
                           "items": {"Manual Flanger": "single"}})
        w = next_unfinished_work(lifecycle.get_task(run_id))
        fresh = [a for a in w["actions"]
                 if "freshness" in str(a.get("question") or "").lower()]
        assert len(fresh) == 1, "repeated saved-copy reads: ONE successor"

    def test_freshness_action_is_not_a_saved_copy_reread(self):
        """The in-turn read loop only dispatches next_actions starting
        with 'read '; the freshness successor targets the LIVE source —
        it must never be executed as a saved-copy reread."""
        from integrations.chat_orchestrator import _job_scope_items  # noqa

        orch_src = open("integrations/chat_orchestrator.py").read()
        tl_src = open("core/task_lifecycle.py").read()
        assert '.startswith("read ")' in orch_src
        assert "re-verify" in tl_src and "live source" in tl_src
        # And a failed verification never resolves the question.
        from core.task_lifecycle import normalize_execution_facts
        facts = normalize_execution_facts({
            "invoked": False, "outcome": "read_failed",
            "served_basis": "none", "failure_stage": "access_denied"})
        assert facts["outcome"] == "read_failed"
