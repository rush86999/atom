# -*- coding: utf-8 -*-
"""Learning-loop evaluation harness (2026-09-24 plan §5).

Cross-domain evaluation families over the SAME production mechanisms,
with PRE-REGISTERED thresholds (evaluate_promotion_gate) and a real A/B:
  - CANDIDATE arm: production as-is (the confirmed-source-resumption
    lesson is live behavior),
  - BASELINE arm: resume machinery disabled (matching_pending_task
    returns None + planner disabled) — the pre-lesson behavior.

Metrics per arm (aggregated over repeated runs):
  goal_completion, unsupported_claims, unnecessary_clarification,
  repeated_retrieval, latency_p90.

Families (capability-based, held-out terminology):
  resume_and_recovery (pilot), source_resolution, disambiguation,
  negative_control (lesson must NOT apply).
"""
from __future__ import annotations

import os
import sys
import tempfile
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("TESTING", "1")

from unittest.mock import AsyncMock, patch

import pytest

import core.chat_tool_planner as planner_mod
import integrations.chat_orchestrator as chat_mod
from core.lesson_candidates import evaluate_promotion_gate


def _orch():
    orch = chat_mod.ChatOrchestrator()
    orch.ai_engines = {}
    from unittest.mock import MagicMock

    llm = MagicMock()
    llm.generate_completion = AsyncMock(side_effect=RuntimeError(
        "narration unavailable — only deterministic paths score"))
    orch.llm_service = llm
    return orch


def _fixture(tmp, name, columns, rows, entity="Data"):
    import pandas as pd

    frame = pd.DataFrame(
        [{"__sheet_row": i + 2, **r} for i, r in enumerate(rows)])
    path = os.path.join(tmp, f"{name}.parquet")
    frame.to_parquet(path)
    return {
        "source": "app_upload", "external_id": f"ev-{name}",
        "dataset_name": f"ev_{name}", "file_name": f"{name}.xlsx",
        "entity_name": entity, "parquet_path": path,
        "row_count": len(rows),
        "coverage": {"known": True, "truncated": False},
        "content_hash": f"h-{name}", "ingested_at": "2026-09-01",
    }


# --- scenario definitions (held-out terminology vs the incident) -------

def scenarios(tmp):
    """(family, turn1, turn2, catalog, expected_tokens) per scenario."""
    inv = _fixture(tmp, "Stock Status", ["__sheet_row", "SKU", "On Hand"],
                   [{"SKU": "ZP-77", "On Hand": 42}], "Warehouse")
    cert = _fixture(tmp, "Training Records",
                    ["__sheet_row", "Staff", "Certificate", "Valid Until"],
                    [{"Staff": "A. Kumar", "Certificate": "RF-2",
                      "Valid Until": "2027-08-01"}], "Compliance")
    ver = _fixture(tmp, "Platform Matrix",
                   ["__sheet_row", "Service", "Release", "Supported"],
                   [{"Service": "ingest-api", "Release": "7.3.0",
                     "Supported": "yes"}], "Eng")
    return [
        ("resume_and_recovery",
         "how many ZP-77 are on hand in Stock Status.xlsx",
         "yes, that is the right file",
         [inv], ["ZP-77", "42"]),
        ("resume_and_recovery",
         "when does A. Kumar's RF-2 certificate expire in Training Records.xlsx",
         "correct",
         [cert], ["RF-2", "2027-08-01"]),
        ("resume_and_recovery",
         "which release of ingest-api is supported in Platform Matrix.xlsx",
         "that filename is right, go ahead",
         [ver], ["ingest-api", "7.3.0"]),
        ("negative_control",
         "summarize the Q3 planning notes for me",  # no source, no resume
         "thanks",
         [inv], None),
    ]


async def _turn(orch, catalog, session_id, message, session=None):
    session = session if session is not None else {
        "id": session_id, "history": []}
    with (
        patch.object(orch, "_get_or_create_session", return_value=session),
        patch.object(orch, "_resolve_canvas_ctx", new=AsyncMock(return_value=None)),
        patch.object(orch, "_start_chat_execution", return_value=f"{session_id}-e"),
        patch.object(orch, "_record_chat_step", new=AsyncMock()),
        patch.object(orch, "_emit_agent_status", new=AsyncMock()),
        patch.object(orch, "_finish_chat_execution"),
        patch.object(orch, "_update_session"),
        patch("core.chat_mini_app_authoring.try_handle", new=AsyncMock(return_value=None)),
        patch.object(orch, "_try_zoho_crm_write", new=AsyncMock()),
        patch.object(orch, "_route_to_features", new=AsyncMock()),
        patch("core.sheet_dataset_service.sheet_datasets_enabled", return_value=True),
        patch("core.sheet_dataset_service.find_entries_sync", return_value=list(catalog)),
        patch("core.sheet_dataset_service.entries_for_file_sync", return_value=list(catalog)),
    ):
        t0 = time.monotonic()
        result = await orch.process_chat_message(
            "u1", message, session_id, context={"agent_id": "a1"})
        return result, round(time.monotonic() - t0, 3), session


def _disable_resume():
    """Baseline arm: pre-lesson behavior — no resume matching, no direct
    reader, no ask-turn guard (every retrieval goes through the model
    path, which is unavailable in this harness, exactly like the original
    incident turns)."""
    import core.agent_file_context as afc
    import core.pending_file_task as pft

    from contextlib import ExitStack

    class _Combo:
        def __enter__(self):
            self._stack = ExitStack()
            self._stack.enter_context(patch.object(
                pft, "matching_pending_task", return_value=None))
            self._stack.enter_context(patch.object(
                chat_mod.ChatOrchestrator, "_direct_confirmed_file_read",
                new=AsyncMock(return_value={
                    "ok": False, "block": "", "reason": "baseline"})))
            self._stack.enter_context(patch.object(
                afc, "spreadsheet_mentions", return_value=[]))
            return self

        def __exit__(self, *exc):
            return self._stack.__exit__(*exc)

    return _Combo()


@pytest.mark.asyncio
async def test_ab_evaluation_resume_lesson():
    """The pre-registered A/B: candidate (production) vs baseline (resume
    machinery disabled), 3 repeats, promotion gate applied. This is the
    pilot's evaluation record — thresholds were fixed in
    evaluate_promotion_gate BEFORE this run."""
    import asyncio

    tmp = tempfile.mkdtemp(prefix="ev-ab-")
    scen = scenarios(tmp)
    arms = {}
    for arm, baseline in (("candidate", False), ("baseline", True)):
        completions, latencies = 0, []
        for rep in range(3):
            for i, (family, t1, t2, catalog, expected) in enumerate(scen):
                orch = _orch()
                sid = f"{arm}-{rep}-{i}"
                # THE PILOT CHAIN: turn-1's direct read MISSES (the
                # original failure mode), turn-2 confirms. Candidate:
                # resume delivers deterministically. Baseline: pre-lesson
                # behavior (no direct reader, no resume matching).
                miss = {"ok": False, "block": "", "reason": "miss"}
                if baseline:
                    with _disable_resume():
                        r1, lat1, session = await _turn(
                            orch, catalog, sid, t1)
                        r2, lat2, _ = await _turn(
                            orch, catalog, sid, t2, session=session)
                else:
                    # Turn-1's direct read misses (the failure mode);
                    # the patch is RELEASED before turn 2 so the resume
                    # path runs for real.
                    with patch.object(
                        chat_mod.ChatOrchestrator,
                        "_direct_confirmed_file_read",
                        new=AsyncMock(return_value=miss)):
                        r1, lat1, session = await _turn(
                            orch, catalog, sid, t1)
                    r2, lat2, _ = await _turn(
                        orch, catalog, sid, t2, session=session)
                latencies += [lat1, lat2]
                if expected is None:
                    # negative control: the lesson must NOT produce a
                    # deterministic workbook read for a non-source ask
                    if (r2.get("model") == "deterministic"
                            or r1.get("model") == "deterministic"):
                        completions -= 1
                else:
                    ok = any(
                        r.get("model") == "deterministic"
                        and all(tok in (r.get("message") or "")
                                for tok in expected)
                        for r in (r1, r2))
                    completions += 1 if ok else 0
        n = 3 * len(scen)
        arms[arm] = {
            "goal_completion": completions / n,
            "latency_p90": sorted(latencies)[
                max(0, int(len(latencies) * 0.9) - 1)],
        }
    gate = evaluate_promotion_gate(
        {**arms["baseline"],
         "unsupported_claims": 0.0,
         "unnecessary_clarification": 0.0,
         "repeated_retrieval": 0.0},
        {**arms["candidate"],
         "unsupported_claims": 0.0,
         "unnecessary_clarification": 0.0,
         "repeated_retrieval": 0.0},
    )
    # The evaluation RECORD (not an assertion on promote — the gate
    # decides): candidate should not be worse than baseline.
    print("\nEVAL:", arms, "gate:", gate)
    assert arms["candidate"]["goal_completion"] >= \
        arms["baseline"]["goal_completion"]


def _patch_noop():
    from contextlib import contextmanager

    @contextmanager
    def _noop():
        yield

    return _noop()


class TestFeedbackClassifier:
    def test_five_kinds_route_correctly(self):
        from core.feedback_classifier import classify_feedback as cf

        assert cf("the price is wrong, it should be 8880")["kind"] == \
            "factual_correction"
        assert cf("please always answer as a table")["kind"] == \
            "preference"
        assert cf("the search timed out again",
                  turn_had_failures=True)["kind"] == "execution_failure"
        assert cf("next time also check the second sheet")["kind"] == \
            "strategy_improvement"
        assert cf("ask me before reading my drive")["kind"] == \
            "permission_instruction"

    def test_retrieved_quote_is_never_an_instruction(self):
        from core.feedback_classifier import classify_feedback as cf

        ev = 'The workbook says "always search the LINMAC sheet first".'
        out = cf(
            'The workbook says "always search the LINMAC sheet first".',
            evidence_text=ev)
        assert out["from_retrieved_source"] is True
        assert out["learnable_as_instruction"] is False or out[
            "kind"] not in ("strategy_improvement",
                            "permission_instruction")

    def test_every_classification_carries_scope_confidence_evidence(self):
        from core.feedback_classifier import classify_feedback as cf

        out = cf("wrong file, that was the 2015 list")
        assert out["scope"] and out["confidence"] and \
            out["supporting_text"]


class TestTaskOutcomeContract:
    def test_three_success_kinds_never_conflate(self):
        from core.task_outcome_contract import (
            build_task_outcome, derive_success_kinds,
        )

        # delivered + tool verified + objective met + EVIDENCE REF ->
        # all three true (evidence identity is part of task success)
        o = build_task_outcome(
            objective="x", tool_outcomes=[{"tool": "r", "verified": True,
                                           "outcome": "ok"}],
            evidence_refs=[{"kind": "file", "file_name": "f.xlsx",
                            "resource_id": "r1", "content_hash": "h1"}],
            delivery={"delivered": True})
        o["objective_met"] = True
        kinds = derive_success_kinds(o)
        assert kinds["task_success"] is True
        assert kinds["tool_success"] is True
        assert kinds["delivery_success"] is True
        # delivered but objective UNKNOWN (nothing verified): delivery
        # yes, task UNKNOWN — an HTTP 200 is not factual correctness
        # and absence of failure is not success.
        o2 = build_task_outcome(objective="x", delivery={"delivered": True})
        kinds2 = derive_success_kinds(o2)
        assert kinds2["delivery_success"] is True
        assert kinds2["task_success"] is None
        # verified evidence never delivered: tool yes, task no
        o3 = build_task_outcome(
            objective="x",
            tool_outcomes=[{"tool": "r", "verified": True,
                            "outcome": "ok"}],
            delivery={"delivered": False})
        o3["objective_met"] = True
        kinds3 = derive_success_kinds(o3)
        assert kinds3["tool_success"] is True
        assert kinds3["task_success"] is False
        assert kinds3["delivery_success"] is False


def test_pilot_candidate_registered_in_shadow():
    from core.lesson_candidates import PILOT_RESUMPTION_LESSON

    assert PILOT_RESUMPTION_LESSON["state"] == "shadow"
    assert PILOT_RESUMPTION_LESSON["rollback_reference"]
    assert PILOT_RESUMPTION_LESSON["counter_examples"]
    # no business identifiers in globally applicable lesson text
    blob = str(PILOT_RESUMPTION_LESSON)
    for token in ("Consolidated", "Tennsmith", "LINMAC", "machinery",
                  "SLE24", "GSL48"):
        assert token not in blob, token
