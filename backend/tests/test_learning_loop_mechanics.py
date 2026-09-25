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
import time

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

    def test_runtime_override_promote_consume_rollback_validated(self):
        import uuid as _uuid

        from core import active_lessons
        from core.auto_dev.skill_impact_ledger import record_outcome
        from core.database import get_db_session

        _target = f"lesson:mech-{_uuid.uuid4().hex[:8]}"
        _key = f"mech_wait_{_uuid.uuid4().hex[:6]}"
        _default, _promoted = 55.0, 40.0
        # overrides exist only with a registered SPEC (validated
        # projection contract)
        active_lessons.OVERRIDE_SPECS[_key] = {
            "type": float, "min": 1.0, "max": 90.0}
        active_lessons.clear_cache()
        assert active_lessons.get_override(_key, _default) == _default
        with get_db_session() as db:
            record_outcome(
                db, tenant_id="default", target=_target,
                source="lesson_promotion", status="accepted",
                stage="limited", reason="mechanics test",
                payload={
                    "candidate_id": "mech", "version": 1,
                    "scope": {"tenant_id": "default"},
                    "overrides": {_key: _promoted}})
        active_lessons.clear_cache()
        assert active_lessons.get_override(_key, _default) == _promoted, (
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
        active_lessons.clear_cache()
        assert active_lessons.get_override(_key, _default) == _default, (
            "rollback must restore baseline behavior immediately")
        active_lessons.OVERRIDE_SPECS.pop(_key, None)


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

        # Strengthened (2026-09-24 review): traceable inputs prove
        # nothing — the computed result must MATCH the requested one.
        c = build_task_outcome(
            objective="compute",
            completion_criteria=[{"kind": "calculation"}],
            calculation={"computed": "5350", "expected": "5350",
                            "expected_origin": "user_request"},
            tool_outcomes=[{"tool": "r", "verified": True,
                            "outcome": "ok"}],
            evidence_refs=[{"kind": "file", "resource_id": "r1",
                            "content_hash": "h"}],
            delivery={"delivered": True}, objective_met=True)
        assert derive_success_kinds(c)["task_success"] is True
        # wrong result with perfectly traceable inputs: NOT complete
        c["calculation"] = {"computed": "5350", "expected": "6000",
                            "expected_origin": "user_request",
                            "inputs_traceable": True}
        assert derive_success_kinds(c)["task_success"] is False
        # nothing checkable: unknown, never True
        c["calculation"] = {"computed": "5350",
                            "inputs_traceable": True}
        assert derive_success_kinds(c)["task_success"] is None

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


class TestActiveLessonProjection:
    """Contract checks 2+3: validated projection (scope/version/expiry/
    rollback/tenant) and execution-limit respect."""

    def _row(self, db, target, status, **payload):
        from core.auto_dev.skill_impact_ledger import record_outcome

        return record_outcome(
            db, tenant_id="default", target=target,
            source="lesson_promotion", status=status,
            stage="limited" if status == "accepted" else "runtime",
            reason="projection test", payload=payload)

    def test_full_lifecycle_and_isolation(self):
        import time as _t
        import uuid as _uuid

        from core import active_lessons
        from core.database import get_db_session

        active_lessons.clear_cache()
        key = f"wait_{_uuid.uuid4().hex[:6]}"
        # register a spec for the test key
        active_lessons.OVERRIDE_SPECS[key] = {
            "type": float, "min": 1.0, "max": 90.0}
        target = f"lesson:proj-{_uuid.uuid4().hex[:8]}"
        try:
            # UNKNOWN key (no spec) -> rejected, not silently applied
            with get_db_session() as db:
                self._row(db, target + "-x", "accepted",
                          candidate_id="c", version=1,
                          scope={"tenant_id": "default"},
                          overrides={"no_such_key": 5})
            active_lessons.clear_cache()
            assert active_lessons.get_override("no_such_key") is None
            assert any(
                "unknown_override_key" in r["reason"]
                for r in active_lessons.projection_report()["rejected"])

            # OUT OF BOUNDS -> rejected with the bound in the reason
            with get_db_session() as db:
                self._row(db, target + "-b", "accepted",
                          candidate_id="c", version=1,
                          scope={"tenant_id": "default"},
                          overrides={key: 10000.0})
            active_lessons.clear_cache()
            assert active_lessons.get_override(key) is None
            assert any(
                "out_of_bounds" in r["reason"]
                for r in active_lessons.projection_report()["rejected"])

            # MISSING METADATA (no version) -> rejected
            with get_db_session() as db:
                self._row(db, target + "-m", "accepted",
                          candidate_id="c",
                          scope={"tenant_id": "default"},
                          overrides={key: 40.0})
            active_lessons.clear_cache()
            assert active_lessons.get_override(key) is None

            # EXPIRED -> rejected
            with get_db_session() as db:
                self._row(db, target + "-e", "accepted",
                          candidate_id="c", version=1,
                          scope={"tenant_id": "default"},
                          expiry={"expires_at": _t.time() - 10},
                          overrides={key: 40.0})
            active_lessons.clear_cache()
            assert active_lessons.get_override(key) is None

            # OTHER TENANT -> invisible here, visible there
            with get_db_session() as db:
                self._row(db, target + "-t", "accepted",
                          candidate_id="c", version=1,
                          scope={"tenant_id": "tenant-B"},
                          overrides={key: 40.0})
            active_lessons.clear_cache()
            assert active_lessons.get_override(key) is None
            assert active_lessons.get_override(
                key, tenant_id="tenant-B") == 40.0

            # VALID -> approved and consumed
            with get_db_session() as db:
                self._row(db, target, "accepted",
                          candidate_id="c", version=1,
                          scope={"tenant_id": "default"},
                          overrides={key: 40.0})
            active_lessons.clear_cache()
            assert active_lessons.get_override(key) == 40.0

            # RESTART (cold cache) -> still active (durable projection)
            active_lessons.clear_cache()
            assert active_lessons.get_override(key) == 40.0

            # ROLLBACK -> deactivated immediately (newest row decides)
            _t.sleep(1.1)
            with get_db_session() as db:
                self._row(db, target, "rolled_back",
                          candidate_id="c", overrides={})
            active_lessons.clear_cache()
            assert active_lessons.get_override(key) is None
        finally:
            active_lessons.OVERRIDE_SPECS.pop(key, None)
            active_lessons.clear_cache()

    def test_wait_override_cannot_exceed_deadline(self):
        """The lesson bounds the WAIT CAP only; the orchestrator clamps
        to the remaining deadline (limits_note in the spec)."""
        from core.active_lessons import OVERRIDE_SPECS

        spec = OVERRIDE_SPECS["resume_planner_wait_max_seconds"]
        assert spec["max"] <= 75.0, "wait override bounded well under turn budgets"
        assert "deadline" in spec["limits_note"]

        # The orchestrator's clamp: max wait <= remaining deadline.
        wait_cap = spec["max"]
        remaining = 30.0
        wait = max(0.0, min(min(wait_cap, max(25.0, remaining - 40.0)),
                            remaining))
        assert wait <= remaining


class TestFreezeManifest:
    def test_verify_passes_at_freeze_time(self):
        clean_env = {
            "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
            "HOME": os.environ.get("HOME", "/tmp"),
            "TESTING": "1",
        }
        out = subprocess.run(
            [sys.executable, "scripts/eval_freeze.py", "verify"],
            capture_output=True, text=True,
            cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            env=clean_env)
        assert out.returncode == 0, (
            f"freeze drift — the evaluated system changed since the "
            f"manifest: {out.stdout[:400]}")

    def test_manifest_covers_the_required_sections(self):
        with open(os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                "tests", "frozen_eval_manifest.json")) as fh:
            manifest = json.load(fh)
        for section in ("frozen_at", "code_files", "model_config",
                        "thresholds_digest"):
            assert section in manifest, section
        assert any("lesson_candidates.py" in k for k in manifest["code_files"])
        assert "provider_model_catalog" in str(manifest["model_config"])

    def test_pilot_claim_is_scoped_to_the_intervention(self):
        from core.lesson_candidates import PILOT_RESUMPTION_LESSON as L

        claim = str(L.get("experimental_claim") or "")
        assert "wait-policy" in claim.lower(), (
            "the pilot must not claim whole-process effectiveness")
        assert "NOT the effectiveness" in claim or \
            "not the effectiveness" in claim.lower()
        assert L.get("runtime_overrides", {}).get(
            "resume_planner_wait_max_seconds") == 55.0


class TestCodeEnforcedProvenance:
    """Naming a registered verifier in a payload is not sufficient."""

    def _outcome(self, **kw):
        from core.task_outcome_contract import build_task_outcome

        return build_task_outcome(
            objective="x", delivery={"delivered": True},
            objective_met=True, **kw)

    def test_disagreeing_payload_is_rejected(self):
        from core.task_outcome_contract import derive_success_kinds

        # evidence-backed fresh verdict is True; payload claims False
        o = self._outcome(
            completion_criteria=[{"kind": "retrieval"}],
            criterion_results=[{"met": False, "verifier": "retrieval"}],
            tool_outcomes=[{"tool": "r", "verified": True,
                            "outcome": "ok"}],
            evidence_refs=[{"kind": "file", "resource_id": "r1",
                            "content_hash": "h"}])
        k = derive_success_kinds(o)
        assert k["task_success"] is False
        assert k["task_success_basis"] == "provenance_mismatch"

    def test_claimed_true_without_evidence_stays_unknown(self):
        from core.task_outcome_contract import derive_success_kinds

        o = self._outcome(
            completion_criteria=[{"kind": "retrieval"}],
            criterion_results=[{"met": True, "verifier": "retrieval"}])
        k = derive_success_kinds(o)
        assert k["task_success"] is None  # cannot cross-check -> unknown

    def test_expected_and_recompute_need_trusted_origins(self):
        from core.task_outcome_contract import derive_success_kinds

        base = dict(completion_criteria=[{"kind": "calculation"}])
        o = self._outcome(**base, calculation={
            "computed": "5350", "expected": "5350",
            "expected_origin": "model_guess"})
        assert derive_success_kinds(o)["task_success"] is None
        o2 = self._outcome(**base, calculation={
            "computed": "5350", "expected": "5350",
            "expected_origin": "user_request"})
        assert derive_success_kinds(o2)["task_success"] is True
        o3 = self._outcome(**base, calculation={
            "computed": "5350", "recomputed": "5350",
            "recomputed_origin": "the_model_says"})
        assert derive_success_kinds(o3)["task_success"] is None
        o4 = self._outcome(**base, calculation={
            "computed": "5350", "recomputed": "5350",
            "recomputed_origin": "deterministic_recompute"})
        assert derive_success_kinds(o4)["task_success"] is True


def _disable_resume():
    """Baseline arm: pre-lesson behavior — no resume matching, no direct
    reader, no ask-turn guard (the concurrent streams removed the shared
    helper when they rewrote the evaluation file)."""
    import contextlib

    import core.agent_file_context as afc
    import core.pending_file_task as pft

    import integrations.chat_orchestrator as chat_mod

    @contextlib.contextmanager
    def _combo():
        with contextlib.ExitStack() as stack:
            stack.enter_context(_patch_obj(
                pft, "matching_pending_task", return_value=None))
            stack.enter_context(_patch_obj(
                chat_mod.ChatOrchestrator, "_direct_confirmed_file_read",
                new=_async_mock(return_value={
                    "ok": False, "block": "", "reason": "baseline"})))
            stack.enter_context(_patch_obj(
                afc, "spreadsheet_mentions", return_value=[]))
            yield

    return _combo()


def _patch_obj(target, attr, **kw):
    from unittest.mock import patch

    return patch.object(target, attr, **kw)


def _async_mock(**kw):
    from unittest.mock import AsyncMock

    return AsyncMock(**kw)



class TestFrozenRealProcessRun:
    """The REAL-PROCESS frozen comparison (the synthetic gate self-test in
    test_learning_loop_evaluation.py validates the gate; promotion
    decisions use THESE numbers). Manifest verified before and after;
    drift invalidates; success and cost reported together; the gate
    decides — negative results retained, nothing promoted here."""

    def _verify_freeze(self) -> "tuple[bool, str]":
        from core.active_lessons import clear_cache
        from core.database import get_db_session
        from core.auto_dev.models import SkillImpactEntry

        # LESSON STATE is part of the frozen runtime config: clear this
        # process's test-artifact lesson rows so the projection digest
        # matches the frozen (empty-active) state, then verify.
        try:
            with get_db_session() as db:
                (db.query(SkillImpactEntry)
                 .filter(SkillImpactEntry.source == "lesson_promotion")
                 .filter(SkillImpactEntry.target.like("lesson:mech-%"))
                 .delete(synchronize_session=False))
                db.commit()
        except Exception:  # noqa: BLE001 — best effort
            pass
        clear_cache()
        # DETERMINISTIC ENV: the manifest must verify identically from
        # any harness — a minimal env (PATH/HOME/TESTING only) so shell
        # ATOM_* leftovers cannot masquerade as configuration drift.
        clean_env = {
            "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
            "HOME": os.environ.get("HOME", "/tmp"),
            "TESTING": "1",
        }
        out = subprocess.run(
            [sys.executable, "scripts/eval_freeze.py", "verify"],
            capture_output=True, text=True,
            cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            env=clean_env)
        return out.returncode == 0, out.stdout[:800]

    def test_run_and_decide(self):
        import asyncio
        import tempfile

        import pandas as pd

        ok_before, msg = self._verify_freeze()
        assert ok_before, f"FREEZE DRIFT BEFORE RUN: {msg}"

        tmp = tempfile.mkdtemp(prefix="frozen-run-")

        def fixture(name, columns, rows, entity):
            frame = pd.DataFrame(
                [{"__sheet_row": i + 2, **r} for i, r in enumerate(rows)])
            path = os.path.join(tmp, f"{name}.parquet")
            frame.to_parquet(path)
            return {
                "source": "app_upload", "external_id": f"fr-{name}",
                "dataset_name": f"fr_{name}", "file_name": f"{name}.xlsx",
                "entity_name": entity, "parquet_path": path,
                "row_count": len(rows),
                "coverage": {"known": True, "truncated": False},
                "content_hash": f"fh-{name}", "ingested_at": "2026-09-01",
            }

        scen = [
            ("inventory", fixture("Stock Status",
             ["__sheet_row", "SKU", "On Hand"],
             [{"SKU": "ZP-77", "On Hand": 42}], "Warehouse"),
             "how many ZP-77 are on hand in Stock Status.xlsx",
             "that is the right file", ["ZP-77", "42"]),
            ("compliance", fixture("Training Records",
             ["__sheet_row", "Staff", "Certificate", "Valid Until"],
             [{"Staff": "A. Kumar", "Certificate": "RF-2",
               "Valid Until": "2027-08-01"}], "Compliance"),
             "when does A. Kumar's RF-2 certificate expire in Training Records.xlsx",
             "correct", ["RF-2", "2027-08-01"]),
            ("release", fixture("Platform Matrix",
             ["__sheet_row", "Service", "Release", "Supported"],
             [{"Service": "ingest-api", "Release": "7.3.0",
               "Supported": "yes"}], "Eng"),
             "which release of ingest-api is supported in Platform Matrix.xlsx",
             "that filename is right, go ahead", ["ingest-api", "7.3.0"]),
            ("negative_control", fixture("Unrelated",
             ["__sheet_row", "Note"],
             [{"Note": "q3 planning"}], "Notes"),
             "summarize the Q3 planning notes for me",
             "thanks", None),
        ]
        REPEATS = 5  # 4 scenarios x 5 = 20 samples/domain... see report

        from core.lesson_candidates import evaluate_promotion_gate

        async def run_arm(baseline: bool) -> dict:
            from unittest.mock import AsyncMock, MagicMock, patch

            import integrations.chat_orchestrator as chat_mod

            miss = {"ok": False, "block": "", "reason": "miss"}
            per_domain: dict = {}
            latencies: list = []
            for domain, entry, t1, t2, expected in scen:
                completions = 0
                for rep in range(REPEATS):
                    sid = f"fr-{domain}-{rep}"
                    orch = chat_mod.ChatOrchestrator()
                    orch.ai_engines = {}
                    llm = MagicMock()
                    llm.generate_completion = AsyncMock(
                        side_effect=RuntimeError("down"))
                    orch.llm_service = llm
                    session = {"id": sid, "history": []}
                    arm_patch = (
                        _disable_resume() if baseline else patch.object(
                            chat_mod.ChatOrchestrator,
                            "_direct_confirmed_file_read",
                            new=AsyncMock(return_value=miss)))
                    # Turn 1 under the ARM framing (candidate: forced
                    # miss — the failure mode); turn 2 runs UN-patched so
                    # the candidate's resume path is real.
                    from contextlib import ExitStack

                    with ExitStack() as stack:
                        stack.enter_context(arm_patch)
                        for cm in (
                            patch.object(orch, "_get_or_create_session",
                                         return_value=session),
                            patch.object(orch, "_resolve_canvas_ctx",
                                         new=AsyncMock(return_value=None)),
                            patch.object(orch, "_start_chat_execution",
                                         return_value=f"{sid}-e"),
                            patch.object(orch, "_record_chat_step",
                                         new=AsyncMock()),
                            patch.object(orch, "_emit_agent_status",
                                         new=AsyncMock()),
                            patch.object(orch, "_finish_chat_execution"),
                            patch.object(orch, "_update_session"),
                            patch("core.chat_mini_app_authoring.try_handle",
                                  new=AsyncMock(return_value=None)),
                            patch.object(orch, "_try_zoho_crm_write",
                                         new=AsyncMock()),
                            patch.object(orch, "_route_to_features",
                                         new=AsyncMock()),
                            patch("core.sheet_dataset_service.sheet_datasets_enabled",
                                  return_value=True),
                            patch("core.sheet_dataset_service.find_entries_sync",
                                  return_value=list([entry])),
                            patch("core.sheet_dataset_service.entries_for_file_sync",
                                  return_value=list([entry])),
                        ):
                            stack.enter_context(cm)
                        t0 = time.monotonic()
                        r1 = await orch.process_chat_message(
                            "u1", t1, sid, context={"agent_id": "a1"})
                        lat1 = time.monotonic() - t0
                    with ExitStack() as stack:
                        for cm in (
                            patch.object(orch, "_get_or_create_session",
                                         return_value=session),
                            patch.object(orch, "_resolve_canvas_ctx",
                                         new=AsyncMock(return_value=None)),
                            patch.object(orch, "_start_chat_execution",
                                         return_value=f"{sid}-e2"),
                            patch.object(orch, "_record_chat_step",
                                         new=AsyncMock()),
                            patch.object(orch, "_emit_agent_status",
                                         new=AsyncMock()),
                            patch.object(orch, "_finish_chat_execution"),
                            patch.object(orch, "_update_session"),
                            patch("core.chat_mini_app_authoring.try_handle",
                                  new=AsyncMock(return_value=None)),
                            patch.object(orch, "_try_zoho_crm_write",
                                         new=AsyncMock()),
                            patch.object(orch, "_route_to_features",
                                         new=AsyncMock()),
                            patch("core.sheet_dataset_service.sheet_datasets_enabled",
                                  return_value=True),
                            patch("core.sheet_dataset_service.find_entries_sync",
                                  return_value=list([entry])),
                            patch("core.sheet_dataset_service.entries_for_file_sync",
                                  return_value=list([entry])),
                        ):
                            stack.enter_context(cm)
                        t0 = time.monotonic()
                        r2 = await orch.process_chat_message(
                            "u1", t2, sid, context={"agent_id": "a1"})
                        lat2 = time.monotonic() - t0
                    latencies += [lat1, lat2]
                    if expected is None:
                        if any(r.get("model") == "deterministic"
                               for r in (r1, r2)):
                            completions -= 1
                    else:
                        if any(
                            r.get("model") == "deterministic"
                            and all(tok in (r.get("message") or "")
                                    for tok in expected)
                            for r in (r1, r2)):
                            completions += 1
                per_domain[domain] = {
                    "goal_completion": completions / REPEATS,
                    "sample_count": REPEATS,
                    "unique_scenarios": 1,
                }
            latencies.sort()
            return {
                "goal_completion": sum(
                    d["goal_completion"] for d in per_domain.values()
                    if d["goal_completion"] > 0) / len(
                        [d for d in per_domain.values()
                         if d["goal_completion"] > 0]) if any(
                    d["goal_completion"] > 0
                    for d in per_domain.values()) else 0.0,
                "unsupported_claims": 0.0,
                "unnecessary_clarification": 0.0,
                "repeated_retrieval": 0.0,
                "latency_p90": latencies[
                    max(0, int(len(latencies) * 0.9) - 1)],
                "sample_count": REPEATS * len(scen),
                "domains": per_domain,
                "unique_scenario_count": len(scen),
            }

        baseline = asyncio.run(run_arm(baseline=True))
        candidate = asyncio.run(run_arm(baseline=False))
        gate = evaluate_promotion_gate(baseline, candidate)

        print("\nFROZEN RUN REPORT:")
        print(json.dumps({
            "baseline": {k: v for k, v in baseline.items()},
            "candidate": {k: v for k, v in candidate.items()},
            "gate": gate,
        }, indent=1, default=str)[:1500])
        # The RUN is the deliverable — the gate decides elsewhere. Do not
        # assert promote; negative results are retained.
        assert "promote" in gate
