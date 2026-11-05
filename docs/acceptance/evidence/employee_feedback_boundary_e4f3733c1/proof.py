#!/usr/bin/env python3
"""Fresh-session proof for the feedback write-binding and cross-task receipt.

Runs against a frozen backend extraction (set ATOM_BACKEND_ROOT). Uses a
scratch SQLite table and doubled provider transport only. No live model,
provider, credential, spend or network call.

    ATOM_BACKEND_ROOT=/path/to/backend \
    PYTHONPATH=/path/to/backend TESTING=1 \
    python docs/acceptance/evidence/employee_feedback_boundary_e4f3733c1/proof.py
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

BACKEND_ROOT = Path(
    os.environ.get("ATOM_BACKEND_ROOT", Path.cwd() / "backend")).resolve()
sys.path.insert(0, str(BACKEND_ROOT))
os.environ.setdefault("TESTING", "1")

import pytest  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

import core.database as database  # noqa: E402
from core.database import Base  # noqa: E402
from core.learning_llm_router import LearningBasedRouter  # noqa: E402
from core.llm import learning_router_registry as registry  # noqa: E402
from core.llm.capability_profiles import (  # noqa: E402
    get_profile,
    load_feedback_evidence,
    reset_capability_evidence_cache,
)
from tests.test_employee_business_feedback import (  # noqa: E402
    _FAILED_OUTCOME,
    _configure_pool,
    _context,
    _handler,
    _insert_outcome_row,
    _row_by_id,
    _rows,
    _service,
    _synthetic_result,
    _valid_proposal,
)


def _scratch(monkeypatch):
    db_path = Path("/private/tmp/atom-feedback-boundary-proof.db")
    if db_path.exists():
        db_path.unlink()
    engine = create_engine(
        f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    monkeypatch.setattr(database, "SessionLocal", Session)
    router = object.__new__(LearningBasedRouter)
    LearningBasedRouter.__init__(router, Session())
    monkeypatch.setattr(
        registry, "get_learning_router_instance",
        lambda *args, **kwargs: router)
    return engine, Session


def _write_binding(monkeypatch, db):
    from core.employee_routing_feedback import (
        record_attempt_evaluation,
        record_business_outcome,
    )

    cases = [
        ("wrong_workspace", {"workspace_id": "ws-other"},
         "refused_workspace"),
        ("wrong_tenant", {"tenant_id": "tenant-other"}, "refused_tenant"),
        ("wrong_provider", {"provider": "other-provider"},
         "refused_provider"),
        ("wrong_model", {"model": "other-model"}, "refused_model"),
        ("wrong_profile", {"profile": "other_profile"},
         "refused_profile"),
        ("wrong_version", {"version": "2026-11-03.9"},
         "refused_profile_version"),
        ("missing_workspace", {"workspace_id": ""},
         "refused_missing_scope"),
        ("missing_tenant", {"tenant_id": ""}, "refused_missing_scope"),
    ]
    wrong_scope = []
    for name, overrides, expected in cases:
        generation = f"proof-{name}"
        row_id = _insert_outcome_row(db, generation)
        result = _synthetic_result(
            generation,
            provider=overrides.get("provider", "local_ctrl1234"),
            model=overrides.get("model", "llama3.1:8b"),
            profile=overrides.get("profile", "employee_evidence_selection"),
            version=overrides.get("version", "2026-11-04.1"))
        recorded = asyncio.run(record_attempt_evaluation(
            result, stage="employee_evidence_selection",
            evaluation="failed",
            failure_kind="wrong_evidence_selection",
            workspace_id=overrides.get("workspace_id", "ws-ctrl"),
            tenant_id=overrides.get("tenant_id", "tenant-ctrl")))
        row = _row_by_id(db, row_id)  # fresh session
        wrong_scope.append({
            "case": name,
            "status": recorded["status"],
            "recorded": recorded["recorded"],
            "expected": expected,
            "original_row_success": row.success,
            "original_row_quality": row.quality_satisfied,
            "original_row_business_outcome": (
                (row.prompt_features or {}).get("business_outcome")),
        })

    correct_generation = "proof-correct"
    correct_id = _insert_outcome_row(db, correct_generation)
    before_correct = len(_rows(db))
    correct = asyncio.run(record_business_outcome(
        _synthetic_result(correct_generation),
        stage="employee_evidence_selection",
        outcome=_FAILED_OUTCOME,
        workspace_id="ws-ctrl", tenant_id="tenant-ctrl"))
    correct_row = _row_by_id(db, correct_id)
    after_correct = len(_rows(db))
    correct_result = {
        "status": correct["status"],
        "recorded": correct["recorded"],
        "row_count_before": before_correct,
        "row_count_after": after_correct,
        "inserted_rows": after_correct - before_correct,
        "success": correct_row.success,
        "quality_satisfied": correct_row.quality_satisfied,
        "cost_preserved": correct_row.actual_cost == 0.0123,
        "latency_preserved": correct_row.actual_latency_ms == 45.6,
        "failure_kind": (
            (correct_row.prompt_features or {}).get("failure_kind")),
    }

    before = len(_rows(db))
    unknown = asyncio.run(record_attempt_evaluation(
        _synthetic_result("proof-does-not-exist"),
        stage="employee_evidence_selection",
        evaluation="failed", failure_kind="wrong_evidence_selection",
        workspace_id="ws-ctrl", tenant_id="tenant-ctrl"))
    after_unknown = len(_rows(db))

    same_generation = "proof-same-model-two-providers"
    row_a = _insert_outcome_row(
        db, same_generation, provider="provider-a")
    row_b = _insert_outcome_row(
        db, same_generation, provider="provider-b")
    same = asyncio.run(record_attempt_evaluation(
        _synthetic_result(same_generation, provider="provider-b"),
        stage="employee_evidence_selection",
        evaluation="failed", failure_kind="wrong_evidence_selection",
        workspace_id="ws-ctrl", tenant_id="tenant-ctrl"))

    duplicate_generation = "proof-duplicate"
    duplicate_id = _insert_outcome_row(db, duplicate_generation)
    duplicate_result = _synthetic_result(duplicate_generation)
    first = asyncio.run(record_attempt_evaluation(
        duplicate_result, stage="employee_evidence_selection",
        evaluation="failed", failure_kind="wrong_evidence_selection",
        workspace_id="ws-ctrl", tenant_id="tenant-ctrl"))
    second = asyncio.run(record_attempt_evaluation(
        duplicate_result, stage="employee_evidence_selection",
        evaluation="failed", failure_kind="wrong_evidence_selection",
        workspace_id="ws-ctrl", tenant_id="tenant-ctrl"))

    concurrent_generation = "proof-concurrent"
    concurrent_id = _insert_outcome_row(db, concurrent_generation)
    concurrent_result = _synthetic_result(concurrent_generation)

    async def _concurrent():
        weak = record_attempt_evaluation(
            concurrent_result, stage="employee_evidence_selection",
            evaluation="satisfied",
            workspace_id="ws-ctrl", tenant_id="tenant-ctrl")
        strong = record_attempt_evaluation(
            concurrent_result, stage="employee_evidence_selection",
            evaluation="failed", failure_kind="wrong_evidence_selection",
            workspace_id="ws-ctrl", tenant_id="tenant-ctrl")
        return await asyncio.gather(weak, strong)

    asyncio.run(_concurrent())
    concurrent_row = _row_by_id(db, concurrent_id)

    return {
        "wrong_or_missing_scope": wrong_scope,
        "correct_binding": correct_result,
        "unknown_generation": {
            "status": unknown["status"],
            "recorded": unknown["recorded"],
            "orphan_rows": after_unknown - before,
        },
        "same_model_two_providers": {
            "status": same["status"],
            "selected_provider_row_updated": (
                _row_by_id(db, row_b).success is False),
            "other_provider_row_unchanged": (
                _row_by_id(db, row_a).success is True),
        },
        "duplicate_evaluation": {
            "first": first["status"],
            "second": second["status"],
            "final_success": _row_by_id(db, duplicate_id).success,
        },
        "concurrent_precedence": {
            "final_success": concurrent_row.success,
            "final_failure_kind": (
                (concurrent_row.prompt_features or {}).get("failure_kind")),
        },
    }


def _child_task_receipt(monkeypatch):
    import core.employee_proposal as ep
    from core.llm.model_provenance import (
        clear_route_attribution,
        set_feedback_id,
        set_routing_profile,
        set_served_route,
    )

    async def child_wait_for(coro, timeout):
        return await asyncio.wait_for(asyncio.create_task(coro), timeout)

    monkeypatch.setattr(
        ep, "asyncio",
        SimpleNamespace(wait_for=child_wait_for,
                        TimeoutError=asyncio.TimeoutError))

    class LLM:
        async def generate_structured_response(self, **_kwargs):
            set_served_route("controlled", "model-a")
            set_routing_profile(
                "employee_evidence_selection", "2026-11-04.1")
            set_feedback_id("generation-a")
            return _valid_proposal()

    clear_route_attribution()
    result = asyncio.run(ep.propose_employee_work(
        _context(), llm_service=LLM()))
    return {
        "source": result.get("source"),
        "routing_result_id": result.get("routing_result_id"),
        "served_route": (result.get("routing") or {}).get("served_route"),
        "profile": (result.get("routing") or {}).get("profile"),
        "mode": (result.get("routing") or {}).get("mode"),
    }


def _wait_choice(monkeypatch, db):
    from core.employee_routing_feedback import (
        record_attempt_evaluation,
        record_business_outcome,
    )

    pending_generation = "proof-wait-pending"
    pending_id = _insert_outcome_row(
        db, pending_generation, profile="employee_wait_choice")
    pending_result = _synthetic_result(
        pending_generation, profile="employee_wait_choice")
    pending_result["source"] = "model_wait_choice"
    pending = asyncio.run(record_business_outcome(
        pending_result, stage="employee_wait_choice",
        outcome={"objective_met": None},
        workspace_id="ws-ctrl", tenant_id="tenant-ctrl"))
    pending_row = _row_by_id(db, pending_id)
    reset_capability_evidence_cache()
    pending_evidence = load_feedback_evidence(
        get_profile("employee_wait_choice"),
        workspace_id="ws-ctrl", tenant_id="tenant-ctrl")

    validated_generation = "proof-wait-validated"
    validated_id = _insert_outcome_row(
        db, validated_generation, profile="employee_wait_choice")
    validated_result = _synthetic_result(
        validated_generation, profile="employee_wait_choice")
    validated_result.update({
        "source": "model_wait_choice",
        "business_decision_validated": True,
        "business_decision": "wait",
    })
    validated = asyncio.run(record_business_outcome(
        validated_result, stage="employee_wait_choice",
        outcome={"objective_met": None},
        workspace_id="ws-ctrl", tenant_id="tenant-ctrl"))
    validated_row = _row_by_id(db, validated_id)

    rejected_generation = "proof-wait-rejected"
    rejected_id = _insert_outcome_row(
        db, rejected_generation, profile="employee_wait_choice")
    rejected_result = _synthetic_result(
        rejected_generation, profile="employee_wait_choice")
    rejected_result["source"] = "deterministic"
    rejected = asyncio.run(record_attempt_evaluation(
        rejected_result, stage="employee_wait_choice",
        evaluation="failed",
        failure_kind="invalid_plan_reference",
        detail="unnecessary wait: the record is already available",
        workspace_id="ws-ctrl", tenant_id="tenant-ctrl"))
    rejected_row = _row_by_id(db, rejected_id)

    return {
        "parsed_pending": {
            "status": pending["status"],
            "business_outcome": (
                (pending_row.prompt_features or {}).get("business_outcome")),
            "transport_success": pending_row.success,
            "counted_as_capability_sample": (
                "local_ctrl1234/llama3.1:8b" in pending_evidence),
        },
        "validated_decision": {
            "status": validated["status"],
            "business_outcome": (
                (validated_row.prompt_features or {}).get("business_outcome")),
            "scope": (
                (validated_row.prompt_features or {}).get(
                    "business_outcome_scope")),
            "verdict": (
                (validated_row.prompt_features or {}).get("verdict")),
        },
        "rejected_wait": {
            "status": rejected["status"],
            "failure_kind": (
                (rejected_row.prompt_features or {}).get("failure_kind")),
            "business_outcome": (
                (rejected_row.prompt_features or {}).get("business_outcome")),
            "success": rejected_row.success,
        },
    }


def main() -> int:
    mp = pytest.MonkeyPatch()
    engine, _Session = _scratch(mp)
    try:
        handler = _handler()
        _configure_pool(handler, mp)
        service = _service(handler)
        from core.employee_proposal import propose_employee_work

        # Preserve the controlled happy-path decision change.
        from tests.test_employee_business_feedback import (
            _route_aware_instructor,
        )

        invalid_client = handler.clients["local_ctrl1234"]
        for _ in range(3):
            with patch(
                    "core.llm.byok_handler.instructor.from_openai",
                    _route_aware_instructor(
                        [], invalid_client=invalid_client,
                        valid_proposal=_valid_proposal())):
                asyncio.run(propose_employee_work(
                    _context(), llm_service=service))
        reset_capability_evidence_cache()
        selected = []
        with patch(
                "core.llm.byok_handler.instructor.from_openai",
                _route_aware_instructor(
                    selected, invalid_client=invalid_client,
                    valid_proposal=_valid_proposal())):
            next_result = asyncio.run(propose_employee_work(
                _context(), llm_service=service))

        proof = {
            "schema": "atom-feedback-boundary-proof-1",
            "executed_source": os.getenv("ATOM_PROOF_SOURCE", ""),
            "write_binding": _write_binding(mp, {
                "Session": _Session}),
            "child_task_receipt": _child_task_receipt(mp),
            "wait_choice": _wait_choice(mp, {"Session": _Session}),
            "controlled_decision_change": {
                "served_route": (next_result.get("routing") or {}).get(
                    "served_route"),
                "source": next_result.get("source"),
            },
            "boundaries": [
                "scratch SQLite feedback table; fresh sessions read the rows",
                "provider transport doubled; no live model inference",
                "wrong/missing scope/provider/model/profile/version refuse",
                "no orphan business row for an unknown generation",
                "same model on two providers binds to the exact provider",
                "duplicate evaluation is idempotent; stronger verdict wins",
                "child-task wait_for receipt is returned explicitly",
                "parsed wait is unresolved; only a validated decision or "
                "explicit result is satisfactory",
            ],
        }
        out = Path(__file__).with_name("feedback-boundary-proof.json")
        out.write_text(json.dumps(proof, indent=1, default=str) + "\n")
        print(json.dumps(proof, indent=1, default=str)[:5000])
        return 0
    finally:
        reset_capability_evidence_cache()
        mp.undo()
        engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
