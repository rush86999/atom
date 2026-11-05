#!/usr/bin/env python3
"""Fresh-session proof for pending/grounding capability classification.

Runs against a frozen backend extraction (set ATOM_BACKEND_ROOT). Scratch
SQLite and doubled transport only; no live model/provider call.

    ATOM_BACKEND_ROOT=/path/to/backend \
    PYTHONPATH=/path/to/backend TESTING=1 \
    python docs/acceptance/evidence/employee_feedback_classification_f091904ce/proof.py
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

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
    reset_capability_evidence_cache,
)
from tests.test_capability_evidence_classification import (  # noqa: E402
    PROFILE,
    ROUTE,
    _accounting,
    _evidence,
    _insert_outcome_row,
    _legacy_verdict,
    _pending,
    _route,
    _row_by_id,
    _synthetic_result,
)


def _scratch(monkeypatch):
    db_path = Path("/private/tmp/atom-classification-proof.db")
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
    return engine, {"Session": Session}


def _row_view(db, row_id):
    row = _row_by_id(db, row_id)
    features = row.prompt_features or {}
    return {
        "success": row.success,
        "quality_satisfied": row.quality_satisfied,
        "business_outcome": features.get("business_outcome"),
        "business_outcome_scope": features.get("business_outcome_scope"),
        "verdict": features.get("verdict"),
        "failure_kind": features.get("failure_kind"),
        "evaluation_revision": features.get("evaluation_revision"),
    }


def _clear_rows(db):
    from core.models import LLMRoutingFeedback

    with db["Session"]() as session:
        session.query(LLMRoutingFeedback).delete()
        session.commit()


def _case(db, generation, kind, verdict=None):
    _clear_rows(db)
    if kind == "pending":
        row_id, result = _pending(db, generation)
    else:
        row_id = _insert_outcome_row(db, generation, profile=PROFILE)
        result = _synthetic_result(generation, profile=PROFILE)
        result["source"] = "model_wait_choice"

    if verdict:
        _legacy_verdict(
            generation, verdict,
            quality=(verdict not in ("unsupported_figures",)),
            satisfaction=(0.1 if verdict == "unsupported_figures" else 0.9))
    elif kind == "business_failure":
        from core.employee_routing_feedback import (
            record_attempt_evaluation,
        )

        asyncio.run(record_attempt_evaluation(
            result, stage="employee_wait_choice",
            evaluation="failed",
            failure_kind="wrong_evidence_selection",
            workspace_id="ws-ctrl", tenant_id="tenant-ctrl"))
    elif kind == "validated_decision":
        from core.employee_routing_feedback import record_business_outcome

        result.update({
            "business_decision_validated": True,
            "business_decision": "wait",
        })
        asyncio.run(record_business_outcome(
            result, stage="employee_wait_choice",
            outcome={"objective_met": None},
            workspace_id="ws-ctrl", tenant_id="tenant-ctrl"))
    elif kind == "satisfied_result":
        from core.employee_routing_feedback import record_business_outcome

        asyncio.run(record_business_outcome(
            result, stage="employee_wait_choice",
            outcome={"objective_met": True},
            workspace_id="ws-ctrl", tenant_id="tenant-ctrl"))

    route = _route(_evidence())
    accounting = _accounting(db, row_id)
    return {
        "kind": kind,
        "verdict": verdict,
        "durable_row": _row_view(db, row_id),
        "capability_evidence": {
            "samples": route.get("samples", 0),
            "successes": route.get("successes", 0),
            "quality_successes": route.get("quality_successes", 0),
            "semantic_failures": route.get("semantic_failures", 0),
        },
        "accounting": {
            "generations": accounting["generations"],
            "fabricated": accounting["fabricated"],
            "grounded_ok": accounting["grounded_ok"],
            "evidence_ignored": accounting["evidence_ignored"],
        },
    }


def main() -> int:
    mp = pytest.MonkeyPatch()
    engine, db = _scratch(mp)
    try:
        cases = [
            _case(db, "classify-pending-grounding-ok", "pending",
                  "grounding_ok"),
            _case(db, "classify-pending-grounding-passed", "pending",
                  "grounding_passed"),
            _case(db, "classify-pending-fabrication", "pending",
                  "unsupported_figures"),
            _case(db, "classify-pending-business-failure",
                  "business_failure"),
            _case(db, "classify-validated-decision", "validated_decision"),
            _case(db, "classify-satisfied-result", "satisfied_result"),
            _case(db, "classify-legacy-no-marker", "legacy",
                  "grounding_ok"),
        ]
        proof = {
            "schema": "atom-feedback-classification-proof-1",
            "executed_source": os.getenv("ATOM_PROOF_SOURCE", ""),
            "profile": PROFILE,
            "route": ROUTE,
            "cases": cases,
            "boundaries": [
                "scratch SQLite feedback table; fresh sessions read the rows",
                "doubled transport; no live model inference",
                "grounding-only pending work is excluded from capability success",
                "fabrication/business failure stay observable",
                "validated decision and satisfied result still contribute",
                "legacy no-business-marker rows keep compatibility",
                "durable row, capability evidence and accounting checked separately",
            ],
        }
        out = Path(__file__).with_name("classification-proof.json")
        out.write_text(json.dumps(proof, indent=1, default=str) + "\n")
        print(json.dumps(proof, indent=1, default=str)[:5000])
        return 0
    finally:
        reset_capability_evidence_cache()
        mp.undo()
        engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
