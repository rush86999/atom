# -*- coding: utf-8 -*-
"""Row-context reads: the first-failed boundary must be visible.

Live A9 (val-A9-c4b73, run 8f1ca884) recorded TEN row-context reads of the
CORRECT row — Tennsmith /A101, identity column MODEL NO., identity cell
A101 — every one ``read_returned_no_receipt`` with ``items: {}`` and
``findings: []``. The isolated drive of the same row binds 6 price
candidates. The divergence was never the candidates.

Root cause: the job's field contract was EMPTY (``task_revision.
requested_fields: []``) and so was the successor's. ``_bind_row_fields``
binds PER REQUESTED FIELD, so zero fields bind nothing regardless of how
well the row reads. ``_resolve_field_specs`` documents that an empty
contract is UNRESOLVED SCOPE and "the caller surfaces the question"; the
caller never did, so an impossible read was dispatched and reported as
receipt-less.

These pins hold the contract: the cause is named, the attempted inputs
reach the operation record, and nothing is silently skipped.
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

TENNSMITH_ROW = {
    "MODEL NO.": "SLE24-16",
    "Description": "Single Wheel Slitter",
    "U.S. LIST": "8,984",
    "U.S. COST": "7,100",
    "CANADIAN COST": "9,450",
    "DEALER CODE": "K",
}


@pytest.fixture
def lifecycle(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path}/rowread_diag.db")
    for table in (GoalObjective.__table__, GoalRun.__table__,
                  TaskOperationRecord.__table__):
        table.create(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    return TaskLifecycle(
        GoalRunService(workspace_id="ws", tenant_id="t",
                       session_factory=factory),
        GoalService(workspace_id="ws", tenant_id="t",
                    session_factory=factory))


def _row_result(row):
    return {"headers": list(row.keys()), "row": row}


def _act(**over):
    act = {
        "item": "SLE24-16",
        "file": "Consolidated Price List 2019.xlsx",
        "candidates": [{"sheet": "Tennsmith ", "row": 101,
                        "identity_column": "MODEL NO.",
                        "identity_cell": "A101"}],
        "identity_context": "chained required-source lookup: outlook",
        "requested_fields": [],
    }
    act.update(over)
    return act


def _prepare(lifecycle, monkeypatch, row):
    """Seed one open read question and stub the row reader + the
    settlement fence (the fence itself is not under test here)."""
    from core.task_lifecycle import begin_retrieval_turn, record_read_outcome

    run_id, op = begin_retrieval_turn(
        lifecycle, {"id": "s1"}, "conv-diag", "verify pricing", "e1")
    record_read_outcome(
        lifecycle, run_id, op, structured_result=None, freshness=None,
        execution=None, extra_questions=[{
            "item": "SLE24-16", "kind": "verification",
            "question": "SLE24-16 is carried by W.xlsx — not yet read",
            "evidence": "vt", "next_action": "read W.xlsx for SLE24-16",
            "inputs": {"item": "SLE24-16", "file": "W.xlsx"}}])
    monkeypatch.setattr(
        "core.sheet_dataset_service.read_sheet_row_sync",
        (lambda *a, **kw: _row_result(row)) if row is not None
        else (lambda *a, **kw: None))
    import core.task_lifecycle as _tl
    monkeypatch.setattr(_tl, "resolve_unresolved_questions_fenced",
                        lambda *a, **kw: True)
    return run_id


async def _run(lifecycle, run_id, act):
    from core import research_continuation as rc
    return await rc._execute_row_read(
        lifecycle, run_id, "u1", "ws", act, [], agent_lessons=[])


@pytest.mark.asyncio
async def test_empty_field_contract_is_scope_not_receipt_less(
        lifecycle, monkeypatch):
    """The live A9 shape: correct row, empty field contract. The read must
    report the SCOPE gap by name, not a bare read_returned_no_receipt."""
    run_id = _prepare(lifecycle, monkeypatch, TENNSMITH_ROW)
    out = await _run(lifecycle, run_id, _act())
    assert out["statuses"]["SLE24-16"] == "scope_missing_fields", out
    joined = " ".join(out["evidence"])
    assert "field contract is EMPTY" in joined, joined
    assert "Tennsmith" in joined and "101" in joined, (
        "the attempted location must be named: %s" % joined)

    task = lifecycle.get_task(run_id)
    scope_qs = [q for q in (task.get("task_revision") or {}).get(
        "unresolved") or []
                if str(q.get("question") or "").startswith("which fields")]
    assert scope_qs, "an empty contract must surface the documented question"
    assert scope_qs[0]["kind"] in ("business_decision", "verification"), (
        "the question must be one the ledger can actually store: %r"
        % scope_qs[0].get("kind"))


@pytest.mark.asyncio
async def test_a_named_file_read_that_returns_nothing_names_the_location(
        lifecycle, monkeypatch):
    """The silent `continue` is gone: a named-file read returning None
    says WHICH row of WHICH sheet of WHICH file returned nothing."""
    run_id = _prepare(lifecycle, monkeypatch, None)
    out = await _run(lifecycle, run_id, _act(requested_fields=["price"]))
    assert out["statuses"].get("SLE24-16") != "matched"
    joined = " ".join(out["evidence"])
    assert "returned NOTHING" in joined, joined
    assert "Consolidated Price List 2019.xlsx" in joined
    assert "Tennsmith" in joined and "101" in joined


@pytest.mark.asyncio
async def test_a_field_contract_still_binds_the_row(lifecycle, monkeypatch):
    """Positive control: naming the fields is what makes the SAME row
    bind — proving the A9 divergence was the contract, not the row."""
    from core.typed_fields import PRICING_FIELD

    run_id = _prepare(lifecycle, monkeypatch, TENNSMITH_ROW)
    out = await _run(lifecycle, run_id,
                     _act(requested_fields=[PRICING_FIELD]))
    assert out["statuses"]["SLE24-16"] == "matched", out
    joined = " ".join(out["evidence"])
    assert "8,984" in joined, joined
    assert not any("field contract is EMPTY" in e for e in out["evidence"])


def test_execution_facts_carry_the_diagnostics():
    """normalize_execution_facts used to drop them, leaving an outcome
    string and an empty items map. They must survive."""
    from core.task_lifecycle import normalize_execution_facts

    facts = normalize_execution_facts({
        "invoked": True,
        "outcome": "read_returned_no_receipt",
        "served_basis": "saved_copy",
        "items": {},
        "evidence": ["SLE24-16: row 101 of sheet 'Tennsmith ' returned "
                     "NOTHING from Consolidated Price List 2019.xlsx"],
        "attempted_candidates": [{"sheet": "Tennsmith ", "row": 101,
                                  "identity_column": "MODEL NO.",
                                  "identity_cell": "A101"}],
        "requested_fields": [],
        "identity_context": "chained required-source lookup: outlook",
        "findings": [],
    })
    assert facts["evidence"] and "returned NOTHING" in facts["evidence"][0]
    assert facts["attempted_candidates"][0]["row"] == 101
    assert facts["attempted_candidates"][0]["sheet"] == "Tennsmith "
    assert facts["requested_fields"] == []
    assert "outlook" in facts["identity_context"]


def test_execution_facts_diagnostics_are_bounded():
    """The record states observed facts — it must not become a log dump."""
    from core.task_lifecycle import normalize_execution_facts

    facts = normalize_execution_facts({
        "invoked": True,
        "outcome": "read_returned_no_receipt",
        "evidence": ["x" * 900] * 100,
        "attempted_candidates": [{"sheet": "S", "row": i} for i in range(99)],
        "requested_fields": ["f"] * 99,
    })
    assert len(facts["evidence"]) <= 40
    assert all(len(e) <= 400 for e in facts["evidence"])
    assert len(facts["attempted_candidates"]) <= 12
    assert len(facts["requested_fields"]) <= 12


def test_outcome_vocabulary_is_unchanged():
    """This repair names the cause; it does not mint a new outcome the
    closed vocabulary would have to learn about."""
    from core.task_lifecycle import EXEC_OUTCOMES, normalize_execution_facts

    assert "read_returned_no_receipt" in EXEC_OUTCOMES
    assert "scope_missing_fields" not in EXEC_OUTCOMES
    facts = normalize_execution_facts(
        {"invoked": True, "outcome": "scope_missing_fields"})
    assert facts["outcome"] == "read_failed"
    assert facts["raw_outcome"] == "scope_missing_fields"
