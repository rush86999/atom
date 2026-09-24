# -*- coding: utf-8 -*-
"""Closed-loop mechanics, task-neutral criteria, lesson generalization.

Companion to tests/test_learning_loop_evaluation.py (the frozen
pre-registered A/B): these pin the LOOP plumbing — promotion gate
refusal, runtime override consumption with rollback, the shared
criteria-verifier interface, and cross-schema lesson transfer.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("TESTING", "1")

import pytest


class TestClosedLoopMechanics:
    def test_promotion_refuses_without_passing_eval(self, tmp_path):
        eval_file = tmp_path / "eval.json"
        eval_file.write_text(json.dumps({
            "baseline": {"goal_completion": 0.5, "sample_count": 40},
            "candidate": {"goal_completion": 0.52, "sample_count": 40,
                          "unsupported_claims": 0.0,
                          "unnecessary_clarification": 0.0,
                          "repeated_retrieval": 0.0,
                          "latency_p90": 50.0},
        }))
        out = subprocess.run(
            [sys.executable, "scripts/promote_lesson.py", "promote",
             "lesson-confirmed-source-resumption-001",
             "--eval-file", str(eval_file)],
            capture_output=True, text=True,
            cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            env={**os.environ, "TESTING": "1"})
        assert "REFUSED" in out.stdout or out.returncode == 1

    def test_runtime_override_promote_consume_rollback(self):
        import uuid as _uuid

        from core import lesson_runtime
        from core.auto_dev.skill_impact_ledger import record_outcome
        from core.database import get_db_session

        _target = f"lesson:mech-{_uuid.uuid4().hex[:8]}"
        _key = f"mech_wait_{_uuid.uuid4().hex[:6]}"
        _default, _promoted = 55.0, 40.0
        lesson_runtime.clear_cache()
        assert lesson_runtime.get_override(_key, _default) == _default
        with get_db_session() as db:
            record_outcome(
                db, tenant_id="default", target=_target,
                source="lesson_promotion", status="accepted",
                stage="limited", reason="mechanics test",
                payload={"overrides": {_key: _promoted}})
        lesson_runtime.clear_cache()
        assert lesson_runtime.get_override(_key, _default) == _promoted, (
            "an APPROVED lesson must be consumed at runtime")
        # the ledger's timestamp granularity is 1s — separate the rows so
        # newest-wins ordering is deterministic
        import time as _t

        _t.sleep(1.1)
        with get_db_session() as db:
            record_outcome(
                db, tenant_id="default", target=_target,
                source="lesson_promotion", status="rolled_back",
                stage="runtime", reason="mechanics rollback",
                payload={"overrides": {}})
        lesson_runtime.clear_cache()
        assert lesson_runtime.get_override(_key, _default) == _default, (
            "rollback must restore baseline behavior immediately")


class TestTaskNeutralCriteria:
    def test_retrieval_is_one_verifier(self):
        from core.task_outcome_contract import (
            build_task_outcome, derive_success_kinds,
        )

        o = build_task_outcome(
            objective="x", completion_criteria=[{"kind": "retrieval"}],
            tool_outcomes=[{"tool": "r", "verified": True,
                            "outcome": "ok"}],
            evidence_refs=[{"kind": "file", "resource_id": "r1",
                            "content_hash": "h"}],
            delivery={"delivered": True}, objective_met=True)
        assert derive_success_kinds(o)["task_success"] is True

    def test_calculation_verifier(self):
        from core.task_outcome_contract import (
            build_task_outcome, derive_success_kinds,
        )

        c = build_task_outcome(
            objective="compute",
            completion_criteria=[{"kind": "calculation"}],
            calculation={"computed": "5350", "inputs_traceable": True},
            tool_outcomes=[{"tool": "r", "verified": True,
                            "outcome": "ok"}],
            evidence_refs=[{"kind": "file", "resource_id": "r1",
                            "content_hash": "h"}],
            delivery={"delivered": True}, objective_met=True)
        assert derive_success_kinds(c)["task_success"] is True
        c["calculation"] = {"computed": "5350",
                            "inputs_traceable": False}
        assert derive_success_kinds(c)["task_success"] is False

    def test_unknown_kind_stays_unknown(self):
        from core.task_outcome_contract import (
            build_task_outcome, derive_success_kinds,
        )

        o = build_task_outcome(
            objective="x",
            completion_criteria=[{"kind": "not_yet_registered"}],
            delivery={"delivered": True}, objective_met=True)
        kinds = derive_success_kinds(o)
        assert kinds["task_success"] is None
        assert "no_verifier" in kinds["task_success_basis"]


class TestLessonGeneralization:
    def test_pilot_preconditions_and_counters_are_domain_free(self):
        from core.lesson_candidates import PILOT_RESUMPTION_LESSON as L

        blob = str(L).lower()
        for token in ("consolidated", "tennsmith", "linmac", "machinery",
                      "sle24", "gsl48", "workdrive"):
            assert token not in blob, token
        counters = [c["scenario"].lower()
                    for c in L["counter_examples"]]
        assert any("supersed" in c for c in counters)
        assert any("re-read" in c or "delivered" in c for c in counters)

    def test_transfer_to_renamed_schema(self):
        """Same capability, renamed file/sheet/columns (Polish): the
        resumption machinery is schema-independent."""
        import asyncio
        import tempfile

        import pandas as pd

        tmp = tempfile.mkdtemp(prefix="gen-rx-")
        frame = pd.DataFrame({"__sheet_row": [5],
                              "Item Code": ["AB-9"],
                              "Units Available": [17]})
        path = os.path.join(tmp, "r.parquet")
        frame.to_parquet(path)
        catalog = [{
            "source": "app_upload", "external_id": "rx-1",
            "dataset_name": "rx", "file_name": "Warehouse Snapshot 2026.xlsx",
            "entity_name": "Stan", "parquet_path": path, "row_count": 1,
            "coverage": {"known": True, "truncated": False},
            "content_hash": "hx", "ingested_at": "2026-09-01",
        }]

        async def run():
            from unittest.mock import AsyncMock, MagicMock, patch

            import integrations.chat_orchestrator as chat_mod

            orch = chat_mod.ChatOrchestrator()
            orch.ai_engines = {}
            llm = MagicMock()
            llm.generate_completion = AsyncMock(
                side_effect=RuntimeError("narration down"))
            orch.llm_service = llm
            session = {"id": "rx-s", "history": []}
            with (
                patch.object(orch, "_get_or_create_session",
                             return_value=session),
                patch.object(orch, "_resolve_canvas_ctx",
                             new=AsyncMock(return_value=None)),
                patch.object(orch, "_start_chat_execution",
                             return_value="rx-e"),
                patch.object(orch, "_record_chat_step", new=AsyncMock()),
                patch.object(orch, "_emit_agent_status", new=AsyncMock()),
                patch.object(orch, "_finish_chat_execution"),
                patch.object(orch, "_update_session"),
                patch("core.chat_mini_app_authoring.try_handle",
                      new=AsyncMock(return_value=None)),
                patch.object(orch, "_try_zoho_crm_write",
                             new=AsyncMock()),
                patch.object(orch, "_route_to_features", new=AsyncMock()),
                patch("core.sheet_dataset_service.sheet_datasets_enabled",
                      return_value=True),
                patch("core.sheet_dataset_service.find_entries_sync",
                      return_value=list(catalog)),
                patch("core.sheet_dataset_service.entries_for_file_sync",
                      return_value=list(catalog)),
            ):
                return await orch.process_chat_message(
                    "u1",
                    "how many AB-9 are available in Warehouse Snapshot 2026.xlsx",
                    "rx-s", context={"agent_id": "a1"})

        result = asyncio.run(run())
        assert result.get("model") == "deterministic"
        assert "17" in result["message"]


class TestFeedbackCaptureWiring:
    def test_capture_routes_through_the_classifier(self):
        """The capture service calls the classifier and persists the
        routing on the row (source-pinned: the wiring, not a full DB
        round-trip — capture's pair resolution needs a live session)."""
        import inspect

        from core import exchange_example_service as svc

        src = inspect.getsource(svc.capture_exchange)
        assert "classify_feedback" in src, (
            "capture must classify before learning from feedback")
        assert "feedback_classification" in src, (
            "the classification must be persisted on the row")
        # and the model carries the column
        from core.models import ExchangeExample

        assert hasattr(ExchangeExample, "feedback_classification")
